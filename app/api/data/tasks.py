import logging
from sqlalchemy import func, types
from sqlalchemy.sql.ddl import CreateSchema
from sqlalchemy.dialects.postgresql import UUID

from app import celery, db
from app.models import Workspace, WorkspaceState, Metadata, Family
from app.api.exceptions import WorkerException
from app.helpers.google_api import get_client, get_bucket
from app.helpers.sql import CreateTableAs, DropSchemaIfExists, GrantUsageOnSchema


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
    logger.info('Initializing bucket of workspace %s...', wid)

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
        client = get_client()
        bucket = client.bucket(bucket_name)
        bucket.storage_class = 'REGIONAL'
        bucket.create(client=client, location='europe-west1')
    except Exception as ex:
        # Update database model to set as invalid
        workspace.state = WorkspaceState.INVALID
        db.session.add(workspace)
        db.session.commit()
        raise

    # Update the database model
    workspace.state = WorkspaceState.READY
    workspace.data_url = f'gs://{bucket_name}'
    db.session.add(workspace)
    db.session.commit()


@celery.task()
def delete_workspace(wid):
    logger.info('Deleting workspace %s...', wid)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.DELETING:
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
    workspace.state = WorkspaceState.DELETED
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
            types_schema['size'] = types.Integer
            types_schema['date'] = types.DateTime(timezone=True)

        # 2.2 Create table
        columns = [Metadata.json['id'].astext.cast(UUID).label('id')]
        for k in keys:
            col_k = Metadata.json[k].astext  # TODO: do we need to protect the key names from injection?
            if k in types_schema:
                col_k = col_k.cast(types_schema[k])
            columns.append(col_k.label(k))

        create_table_query = workspace_metadata.filter(Family.name == family.name).with_entities(*columns).subquery()
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

    # Do the committing task

    # TODO: verify conflicts
    logger.warning('No conflict detection implemented!')

    for family in workspace.families.all():
        new_family = family.increment()
        family.version = new_family.version
        family.workspace = None
        db.session.add_all([family, new_family])

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

    # Update the workspace object
    # TODO: consider if the schema be deleted?
    workspace.state = WorkspaceState.READY
    db.session.add(workspace)

    db.session.commit()
