import itertools
import logging
import pathlib

from flask import current_app
from sqlalchemy import func, types
from sqlalchemy.sql.ddl import CreateSchema
from sqlalchemy.dialects.postgresql import UUID

from quetzal.app import celery, db
from quetzal.app.api.exceptions import Conflict, WorkerException
from quetzal.app.helpers.google_api import get_client, get_bucket
from quetzal.app.helpers.sql import CreateTableAs, DropSchemaIfExists, GrantUsageOnSchema
from quetzal.app.models import Family, FileState, Metadata, Workspace, WorkspaceState


logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=10)
def wait_for_workspace(self, wid):
    """ Wait until a workspace is created on the database

    Parameters
    ----------
    wid: int
        Workspace identifier

    Returns
    -------

    """
    logger.info('Waiting for creation of workspace %s ...', wid)

    workspace = Workspace.query.get(wid)
    if workspace is None:
        logger.info('Workspace is not available yet')
        raise self.retry(countdown=1)

    logger.info('Workspace %s is now available', wid)


@celery.task()
def init_workspace(wid):
    """ Initialize the internal representation of a workspace

    Once a request to create a workspace has been accepted, there are some
    operations that may take some time because they are not trivial to
    obtain from the database. This includes:

    1. The reference to the latest the latest *global* metadata entry used
       to determine the default metadata values.
    2. The exact version of the metadata families when they are set to
       ``None``, which means the latest available.

    Parameters
    ----------
    wid: int
        Workspace identifier

    Returns
    -------
    None

    """
    logger.info('Initializing workspace %s...', wid)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.INITIALIZING:
        raise WorkerException('Workspace was not on the expected state')

    # Determine the most recent "global" metadata entry so that the workspace
    # has a reference number from which any new metadata will be ignored
    # TODO: needs to consider the version!
    latest_metadata = (
        db.session.query(Metadata)
        .join(Family)
        .filter_by(workspace=None)
        .order_by(Metadata.id.desc())
        .first()
    )
    logger.info('The latest global metadata is %s', latest_metadata)
    if latest_metadata is None:
        workspace.fk_last_metadata_id = None
    else:
        workspace.fk_last_metadata_id = latest_metadata.id

    # Verify and update family versions so that :
    # - non null version values are verified to exist
    # - null version values are set to the latest available version

    # query that obtains the latest global family (i.e. with null workspace)
    qs_global_families = (
        Family.query
        .filter_by(workspace=None)
    )
    # this is grouped by family name in order to get the latest per family name
    qs_latest_families = (
        qs_global_families
        .distinct(Family.name, Family.version)
        .order_by(Family.name, Family.version.desc())
    )

    for family in workspace.families:
        if family.version == 0:
            # Setting the family version to zero is permitted and does not need
            # any verification; it means that the workspace will not use any
            # preexisting metadata for that family
            logger.info('Family %s left at version 0', family.name)

        elif family.version is not None:
            # Request for a specific version (that is not zero).
            # First, we need to verify that the name and version combination
            # does exist as a global family (i.e. a family that has been
            # commited and therefore has workspace == null)
            exact_family = (
                qs_global_families
                .filter_by(name=family.name, version=family.version)
                .one_or_none()
            )
            if exact_family is None:
                # The specified version does not exist. Abort and set the
                # workspace in an error state
                logger.info('Family %s at version %s does not exist', family.name, family.version)
                db.session.rollback()
                workspace.state = WorkspaceState.INVALID
                db.session.add(workspace)
                db.session.commit()
                raise WorkerException('Invalid family specification')

            # if family.version was not none, then everything is correct
            logger.info('Adding family %s at version %s', family.name, family.version)

        else:
            latest_family = qs_latest_families.filter_by(name=family.name).first()
            if latest_family is None:
                # Family does not exist
                family.version = 0
            else:
                # Family does exist, use the latest version
                family.version = latest_family.version

            logger.info('Family %s at latest version set to version=%d',
                        family.name, family.version)

            # save the family with the updated version number
            db.session.add(family)

    # Commit changes to database
    db.session.commit()


@celery.task()
def init_data_bucket(wid):
    storage_backend = current_app.config['QUETZAL_DATA_STORAGE']
    logger.info('Initializing bucket of workspace %s on backend %s...', wid, storage_backend)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.INITIALIZING:
        raise WorkerException('Workspace was not on the expected state')

    # Do the initialization task
    # TODO: manage exceptions/errors
    # TODO: manage location and storage class through configuration or workspace options
    bucket_name = f'quetzal-ws-{workspace.id}-{workspace.owner.username}-{workspace.name}'

    try:
        if storage_backend == 'GCP':
            data_url = _init_gcp_data_bucket(bucket_name)
        elif storage_backend == 'file':
            data_url = _init_local_data_bucket(bucket_name)
        else:
            raise WorkerException(f'Unknown storage backend {storage_backend}.')
    except Exception as ex:
        # Update database model to set as invalid
        workspace.state = WorkspaceState.INVALID
        db.session.add(workspace)
        db.session.commit()
        raise

    # Update the database model
    workspace.state = WorkspaceState.READY
    workspace.data_url = data_url
    db.session.add(workspace)
    db.session.commit()


def _init_gcp_data_bucket(bucket_name):
    # TODO: manage exceptions/errors
    # TODO: manage location and storage class through configuration or workspace options
    client = get_client()
    bucket = client.bucket(bucket_name)
    bucket.storage_class = 'REGIONAL'
    bucket.create(client=client, location='europe-west1')
    return f'gs://{bucket_name}'


def _init_local_data_bucket(bucket_name):
    basedir = current_app.config['QUETZAL_FILE_USER_DATA_DIR']
    path = pathlib.Path(basedir) / bucket_name
    path.mkdir(mode=0o755, parents=True, exist_ok=False)
    return f'file://{path.resolve()}'


@celery.task()
def delete_workspace(wid, force=False):
    logger.info('Deleting workspace %s...', wid)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.DELETING and not force:
        raise WorkerException('Workspace was not on the expected state')

    # Delete the data bucket and its contents
    if workspace.data_url is not None:
        # TODO: manage exceptions/errors
        client = get_client()
        bucket = get_bucket(workspace.data_url, client=client)

        # Delete all blobs first
        blobs = list(bucket.list_blobs())
        bucket.delete_blobs(blobs)  # TODO: use the on_error for missing blobs

        # Delete the bucket
        bucket.delete()

    # Drop schema used for queries
    if workspace.pg_schema_name is not None:
        db.session.execute(DropSchemaIfExists(workspace.pg_schema_name, cascade=True))

    # Update the database model
    if not force:
        workspace.state = WorkspaceState.DELETED
    else:
        workspace._state = WorkspaceState.DELETED
    workspace.data_url = None
    db.session.add(workspace)
    db.session.commit()


@celery.task()
def scan_workspace(wid):
    logger.info('Scanning workspace %s...', wid)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.SCANNING:
        raise WorkerException('Workspace was not on the expected state')

    # The scanning task consists on the following procedure:
    # 1. create a new database directory (aka schema in postgres)
    # 2. get the workspace metadata
    # 3. for each family f
    # 3.1. determine the type of each column (this is currently not very smart)
    # 3.2. create a table in the directory from a query on the workspace metadata
    #      but only filtering the entries of the family f
    # 3.3. create index on the id column of this table for efficient joins
    # 4. grant permissions on the directory
    # 5. drop previous directory if any

    # create postgres schema
    old_schema = workspace.pg_schema_name
    new_schema = workspace.make_schema_name()
    db.session.execute(CreateSchema(new_schema))

    # 2. For each family
    workspace_metadata = workspace.get_metadata()
    for family in workspace.families.all():

        tmp = workspace_metadata.filter(Family.name == family.name).subquery()
        keys_query = db.session.query(func.jsonb_object_keys(tmp.c.metadata_json)).distinct()
        keys = set(res[0] for res in keys_query.all()) - {'id'}
        logger.info('Keys for family %s are %s', family.name, keys)

        # 2.1 Determine the type of all columns
        # TODO consider this, for the moment, everything is a string
        types_schema = {}
        if family.name == 'base':  # TODO refactor base schema to an external variable
            types_schema['size'] = types.BigInteger
            types_schema['date'] = types.DateTime(timezone=True)

        # 2.2 Create table
        columns = [Metadata.json['id'].astext.cast(UUID).label('id')]
        for k in keys:
            col_k = Metadata.json[k].astext  # TODO: do we need to protect the key names from injection?
            if k in types_schema:
                col_k = col_k.cast(types_schema[k])
            columns.append(col_k.label(k))

        create_table_query = (
            workspace_metadata.filter(Family.name == family.name,
                                      Metadata.json['state'].astext != 'DELETED' if family.name == 'base' else True)
            .with_entities(*columns)
            .subquery()
        )
        family_table_name = f'{new_schema}.{family.name}'
        create_table_statement = CreateTableAs(family_table_name, create_table_query)
        db.session.execute(create_table_statement)

        # TODO: create an index on the id column

    # Set permissions on readonly user to the schema contents
    db.session.execute(GrantUsageOnSchema(new_schema, 'db_ro_user'))

    # Drop previous schema
    if old_schema is not None:
        db.session.execute(DropSchemaIfExists(old_schema, cascade=True))

    # Update the workspace object to have the correct schema and state
    workspace.pg_schema_name = new_schema
    workspace.state = WorkspaceState.READY
    db.session.add(workspace)

    # Commit all changes
    db.session.commit()


@celery.task()
def commit_workspace(wid):
    logger.info('Committing workspace %s...', wid)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.COMMITTING:
        raise WorkerException('Workspace was not on the expected state')

    with db.session.begin_nested():
        # Lock the database so that nothing gets written or read on the database
        db.session.execute(f'LOCK TABLE {Metadata.__table__.name} IN ACCESS EXCLUSIVE MODE;')

        # TODO: verify conflicts
        try:
            _conflict_detection(workspace)
        except Conflict:
            logger.info('Commit failed due to conflict', exc_info=True)
            workspace.state = WorkspaceState.CONFLICT
            db.session.add(workspace)
            db.session.commit()
            return

        # File ids of files that are temporary
        base_family = workspace.families.filter(Family.name == 'base').first()
        files_not_ready = (
            base_family.metadata_set
            .filter(Metadata.json['state'].astext != FileState.READY.name)
            .subquery()
        )

        # Do the committing task:
        # Iterate over all families, but do base family last, because the
        # subquery above files_not_ready takes uses the base family to determine
        # which files are note ready
        families = itertools.chain(
            workspace.families.filter(Family.name != 'base'),
            [base_family]
        )
        for family in families:
            new_family = family.increment()
            family.version = new_family.version
            family.workspace = None
            db.session.add_all([family, new_family])

            # All files that are not READY (they are temporary or deleted) need
            # to be associated with the family of this workspace, not the
            # committed family
            meta_not_ready = (
                family.metadata_set
                .join(files_not_ready, Metadata.id_file == files_not_ready.c.id_file)
            )
            logger.info('Meta that is not ready: %s', meta_not_ready.all())
            for meta in meta_not_ready:
                meta.family = new_family
                db.session.add(meta)

        # update the fk_last_metadata_id:
        # Determine the most recent "global" metadata entry so that the workspace
        # has a reference number from which any new metadata will be ignored
        # TODO: needs to consider the version!
        # TODO: consider refactor into workspace model
        latest_metadata = (
            db.session.query(Metadata)
            .join(Family)
            .filter_by(workspace=None)
            .order_by(Metadata.id.desc())
            .first()
        )
        if latest_metadata is not None:
            workspace.fk_last_metadata_id = latest_metadata.id
        else:
            workspace.fk_last_metadata_id = None

        # Update the global views for public queries
        _update_global_views()

        # Update the workspace object
        # TODO: consider if the schema (ie the postgres view) should be deleted?
        workspace.state = WorkspaceState.READY
        db.session.add(workspace)

    db.session.commit()


def _conflict_detection(workspace):
    # if the workspace families are the latest global families, then
    # there is no conflict
    latest_families = (
        db.session.query(Family.name, func.max(Family.version))
        .filter(Family.fk_workspace_id.is_(None))
        .group_by(Family.name)
    )
    latest_families_dict = {k: v for k, v in latest_families}
    for family in workspace.families:
        if family.name not in latest_families_dict:
            # It's a new family, not known in the global workspace
            continue
        if family.version < latest_families_dict[family.name]:
            # The family is known in the global workspace and it has a greater
            # version: there is a conflict!
            # TODO: improve this, as it is actually simplistic, there could be no conflict
            raise Conflict(f'Family {family.name} is outdated in workspace {workspace.id}.')

    # TODO: more conflict detection is needed


def _update_global_views():
    # TODO: protect with a database lock

    # Create postgres schema
    db.session.execute(DropSchemaIfExists('global_views', cascade=True))
    db.session.execute(CreateSchema('global_views'))

    # Get all the known families
    families = Family.query.filter(Family.fk_workspace_id.is_(None)).distinct(Family.name)
    # This is the metadata entries related to the latest global families
    global_metadata = Metadata.get_latest_global()

    # For each family, create a view/table
    for family in families:
        tmp = global_metadata.filter(Family.name == family.name).subquery()
        keys_query = db.session.query(func.jsonb_object_keys(tmp.c.json)).distinct()
        keys = set(res[0] for res in keys_query.all()) - {'id'}
        logger.info('Keys for family %s are %s', family.name, keys)

        # 2.1 Determine the type of all columns
        # TODO consider this, for the moment, everything is a string
        types_schema = {}
        if family.name == 'base':  # TODO refactor base schema to an external variable
            types_schema['size'] = types.BigInteger
            types_schema['date'] = types.DateTime(timezone=True)

        # 2.2 Create table
        columns = [Metadata.json['id'].astext.cast(UUID).label('id')]
        for k in keys:
            col_k = Metadata.json[k].astext  # TODO: do we need to protect the key names from injection?
            if k in types_schema:
                col_k = col_k.cast(types_schema[k])
            columns.append(col_k.label(k))

        create_table_query = (
            global_metadata.filter(Family.name == family.name,
                                   Metadata.json['state'].astext != 'DELETED' if family.name == 'base' else True)
            .with_entities(*columns)
            .subquery()
        )
        family_table_name = f'global_views.{family.name}'
        create_table_statement = CreateTableAs(family_table_name, create_table_query)
        db.session.execute(create_table_statement)

        # TODO: create an index on the id column

    # Set permissions on readonly user to the schema contents
    db.session.execute(GrantUsageOnSchema('global_views', 'db_ro_user'))
