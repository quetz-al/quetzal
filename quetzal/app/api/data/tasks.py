import copy
import itertools
import logging
import pathlib
import shutil
from urllib.parse import urlparse

from flask import current_app
from sqlalchemy import func, types
from sqlalchemy.sql.ddl import CreateSchema
from sqlalchemy.sql import literal
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.dialects.postgresql import UUID

from quetzal.app import celery, db
from quetzal.app.api.exceptions import Conflict, EmptyCommit, WorkerException
from quetzal.app.helpers.google_api import get_client, get_bucket, get_data_bucket
from quetzal.app.helpers.sql import CreateTableAs, DropSchemaIfExists, GrantUsageOnSchema
from quetzal.app.models import Family, FileState, Metadata, QueryDialect, Workspace, WorkspaceState


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

    # Delete data bucket and its contents
    if workspace.data_url is not None:
        try:
            _delete_bucket(workspace.data_url)
        except Exception as ex:
            # Update database model to set as invalid
            # TODO: add this transition to the workspace state diagram
            workspace.state = WorkspaceState.INVALID
            db.session.add(workspace)
            db.session.commit()
            raise

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


def _delete_bucket(url):
    storage_backend = current_app.config['QUETZAL_DATA_STORAGE']
    if storage_backend == 'GCP':
        _delete_gcp_data_bucket(url)
    elif storage_backend == 'file':
        _delete_local_data_bucket(url)
    else:
        raise WorkerException(f'Unknown storage backend {storage_backend}.')


def _delete_gcp_data_bucket(url):
    data_bucket = current_app.config['QUETZAL_GCP_DATA_BUCKET']
    if url.startswith(data_bucket):
        raise RuntimeError('Refusing to delete the main data bucket')
    client = get_client()
    bucket = get_bucket(url, client=client)

    # Delete all blobs first
    blobs = list(bucket.list_blobs())
    bucket.delete_blobs(blobs)  # TODO: use the on_error for missing blobs

    # Delete the bucket
    bucket.delete()


def _delete_local_data_bucket(url):
    data_bucket = current_app.config['QUETZAL_FILE_DATA_DIR']
    if url.startswith(data_bucket):
        raise RuntimeError('Refusing to delete the main data directory')
    path = urlparse(url).path
    shutil.rmtree(path)  # TODO: consider the on_error?


@celery.task()
def scan_workspace(wid):

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.SCANNING:
        raise WorkerException('Workspace was not on the expected state')

    schema_name = workspace.make_schema_name()
    _scan_create_table_views(workspace, schema_name)
    _scan_create_json_views(workspace, schema_name)

    # Update the workspace object to have the correct schema and state
    workspace.pg_schema_name = schema_name
    workspace.state = WorkspaceState.READY
    db.session.add(workspace)

    # Commit all changes
    db.session.commit()


def _new_schema(workspace, name, suffix):
    # Drop previous schema
    if workspace.pg_schema_name is not None:
        old_schema = workspace.pg_schema_name + suffix
        db.session.execute(DropSchemaIfExists(old_schema, cascade=True))
    # create postgres schema
    new_name = name + suffix
    db.session.execute(CreateSchema(new_name))
    return new_name


def _scan_create_json_views(workspace, schema_name):
    logger.info('Scanning workspace %s to create json views...', workspace.id)

    # The scanning task consists on the following procedure:
    # 1. create a new database directory (aka schema in postgres)
    #    also, drop the previous one if it existed
    # 2. get the workspace metadata
    # 3. for each family f
    # 3.1. create a subquery that selects only the latest metadata of family f
    # 4. join all family queries with the appropriate aliases so that the
    #    column names correspond to the family name
    # 4. grant permissions on the directory
    # 5. drop previous directory if any

    # Drop previous schema and create a new one
    suffix = f'_{QueryDialect.POSTGRESQL_JSON.value}'
    new_schema = _new_schema(workspace, schema_name, suffix)

    # Extract metadata per family
    master_query = _make_json_view_query(workspace.get_metadata(), workspace.families)

    family_table_name = f'{new_schema}.metadata'
    create_table_statement = CreateTableAs(family_table_name, master_query)
    db.session.execute(create_table_statement)

    # Set permissions on readonly user to the schema contents
    db.session.execute(GrantUsageOnSchema(new_schema, 'db_ro_user'))


def _make_json_view_query(metadata_query, families):
    subqueries = []
    sorted_families = sorted(families,
                             key=lambda fam: (-1, fam.name) if fam.name == 'base' else (+1, fam.name))
    for family in sorted_families:
        sub = (
            metadata_query
            .filter(Family.name == family.name)
            .subquery(name=family.name)
        )
        subqueries.append(sub)

    # Make a joined table of all metadata and set the json column to the name of the family
    qbase = subqueries.pop(0)  # the first one is always the base family, due to the sort done before
    joined_query = db.session.query(qbase)
    columns = [qbase.c.metadata_id_file.label('id'), qbase.c.metadata_json.label('base')]
    for q in subqueries:
        joined_query = joined_query.outerjoin((q, qbase.c.metadata_id_file == q.c.metadata_id_file))
        # Here, we are coalescing to set an empty dict to files that do not
        # have an entry for this particular family. This does not apply to the
        # base family because the base family is always present
        columns.append(coalesce(q.c.metadata_json, literal({}, types.JSON)).label(q.name))

    master_query = joined_query.with_entities(*columns).subquery()
    return master_query


def _scan_create_table_views(workspace, schema_name):
    logger.info('Scanning workspace %s to create table views...', workspace.id)

    # The scanning task consists on the following procedure:
    # 1. create a new database directory (aka schema in postgres)
    #    also, drop the previous one if it existed
    # 2. get the workspace metadata
    # 3. for each family f
    # 3.1. determine the type of each column (this is currently not very smart)
    # 3.2. create a table in the directory from a query on the workspace metadata
    #      but only filtering the entries of the family f
    # 3.3. create index on the id column of this table for efficient joins
    # 4. grant permissions on the directory
    # 5. drop previous directory if any

    # Drop previous schema and create a new one
    suffix = f'_{QueryDialect.POSTGRESQL.value}'
    new_schema = _new_schema(workspace, schema_name, suffix)

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


@celery.task()
def commit_workspace(wid):
    logger.info('Committing workspace %s...', wid)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(wid)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.COMMITTING:
        raise WorkerException('Workspace was not on the expected state')

    db.session.begin_nested()  # make a savepoint
    try:
        # Lock the database so that nothing gets written or read on the database
        db.session.execute(f'LOCK TABLE {Metadata.__table__.name} IN ACCESS EXCLUSIVE MODE;')

        # Verify conflicts, raise Conflict if there is any conflict
        _conflict_detection(workspace)

        base_family = workspace.families.filter(Family.name == 'base').first()

        # Move new READY files (not temporary and not deleted) to the data
        # directory. Since creating a new file creates a new base metadata
        # entry, we can get this from the base metadata family of this
        # workspace. But there is an exception when a path is changed: there is
        # no need to copy anything at all
        files_ready = (
            base_family.metadata_set
            .filter(Metadata.json['state'].astext == FileState.READY.name)
        )
        files_deleted = (
            base_family.metadata_set
            .filter(Metadata.json['state'].astext == FileState.DELETED.name)
        )
        files_not_ready = (
            base_family.metadata_set
            .filter(Metadata.json['state'].astext == FileState.TEMPORARY.name)
            .subquery()
        )

        if files_ready.count() + files_deleted.count() == 0:
            raise EmptyCommit
        logger.info('There are %d files to commit', files_ready.count() + files_deleted.count())

        for file_meta in files_ready:
            logger.info('Commit: copying %s ( %s) to data directory',
                        file_meta, file_meta.json['url'])
            new_url = _commit_file(file_meta.json['id'], file_meta.json['url'])
            file_meta.update({'url': new_url})
            db.session.add(file_meta)

        # Do the committing task:
        # Iterate over all families, but do base family last, because the
        # subquery above files_not_ready takes uses the base family to determine
        # which files are not ready
        families = itertools.chain(
            workspace.families.filter(Family.name != 'base'),
            [base_family]
        )
        for family in families:
            new_family = family.increment()
            family.version = new_family.version
            family.workspace = None
            db.session.add_all([family, new_family])

            # All files that are TEMPORARY need to be associated with the
            # family of this workspace, not the committed family
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

        # Everything went ok!
        # TODO: consider if the schema (ie the postgres view) should be deleted?
        workspace.state = WorkspaceState.READY
        db.session.add(workspace)
        db.session.commit()

    except Conflict:
        logger.info('Commit failed due to conflict', exc_info=True)
        db.session.rollback()  # revert to savepoint
        workspace.state = WorkspaceState.CONFLICT
        db.session.add(workspace)

    except EmptyCommit:
        logger.info('Empty commit, nothing to do')
        db.session.rollback()  # revert to savepoint
        workspace.state = WorkspaceState.READY
        db.session.add(workspace)

    except:
        logger.info('Unexpected error on workspace commit, workspace will '
                    'remain in COMMITTING state', exc_info=True)
        db.session.rollback()  # revert to savepoint

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




def _commit_file(file_id, file_url):
    # TODO: move to a file operations file, along with upload/download
    storage_backend = current_app.config['QUETZAL_DATA_STORAGE']
    if storage_backend == 'GCP':
        return _commit_file_gcp(file_id, file_url)
    elif storage_backend == 'file':
        return _commit_file_local(file_id, file_url)
    raise ValueError(f'Unknown storage backend {storage_backend}')


def _commit_file_local(file_id, file_url):
    source_path = pathlib.Path(urlparse(file_url).path)
    target_path = pathlib.Path(current_app.config['QUETZAL_FILE_DATA_DIR']) / file_id
    shutil.copy(str(source_path.resolve()), str(target_path.resolve()))
    return f'file://{target_path.resolve()}'


def _commit_file_gcp(file_id, file_url):
    file_url_parsed = urlparse(file_url)
    data_bucket = get_data_bucket()
    workpace_bucket = get_bucket(file_url)
    source_blob = workpace_bucket.blob(file_url_parsed.path.lstrip('/'))
    new_blob = workpace_bucket.copy_blob(source_blob, data_bucket, file_id)
    return f'gs://{data_bucket.name}/{new_blob.name}'


def merge(ancestor, theirs, mine):
    mine = copy.deepcopy(mine)
    # Aliases for shorter code:
    #
    # a - ... - b      [i.e. global workspace]
    #  \
    #   - ... - c      [i.e. the workspace to commit]
    #
    a, b, c = ancestor, theirs, mine

    keys = set(a) | set(b) | set(c)
    for k in keys:
        if k in a:
            # First global case: the key existed before.
            # Changes are either modification or deletions. However, when the
            # new value equals the ancestor, it means no modification
            # This means that if they key is not found in b or c, it was a deletion.
            if k in b and k in c:
                # Modifications on both branches
                if b[k] == c[k]:
                    # No conflict, same modification or no modification at all
                    pass
                elif a[k] == b[k] and b[k] != c[k]:
                    # No change on b, modification on c. Accept c
                    pass
                elif a[k] == c[k] and b[k] != c[k]:
                    # No change on c, modification on b. Accept b
                    c[k] = b[k]
                else:  # implied: a[k] != b[k] and a[k] != c[k] and b[k] != c[k]
                    # Conflict, both modified the same with different values
                    raise Conflict

            elif k in b:  # implied: k not in c
                # Possible modification in b and certainly deletion on c
                if b[k] != a[k]:
                    # There was a change on b, but c deleted it. Conflict
                    raise Conflict
                else:
                    # There was no change on b, but c deleted it. Accept c
                    pass

            elif k in c:  # implied: k not in b
                # Possible modification on c and certainly deletion on b
                if c[k] != a[k]:
                    # There was a change on c, but b deleted it. Conflict
                    raise Conflict
                else:
                    # There was no change on c, but c deleted it. Accept b
                    del c[k]

        else:
            # Second global case: the key did not exist before.
            # Changes are additions
            # This means that if the key is not found in b or c, it is
            # because these branches did not do anything on this key
            if k in b and k in c:
                # Modification in both branches
                if b[k] == c[k]:
                    # No conflict, same modification
                    pass
                else:  # implied: b[k] != c[k]
                    # Conflict, both modified the same with different values
                    raise Conflict

            elif k in b:  # implied: k not in c
                # Modification on b but c did not do anything
                # Accept whatever change b brings
                c[k] = b[k]

            elif k in c:  # implied: k not in b
                # Modification on c but b did not do anything
                # Accept whatever change c brings
                pass

    return mine


def _update_global_views():
    # TODO: protect with a database lock
    _update_global_table_views(f'global_views_{QueryDialect.POSTGRESQL.value}')
    _update_global_json_views(f'global_views_{QueryDialect.POSTGRESQL_JSON.value}')


def _update_global_table_views(schema_name):
    logger.info('Updating global table views')

    # Create postgres schema
    db.session.execute(DropSchemaIfExists(schema_name, cascade=True))
    db.session.execute(CreateSchema(schema_name))

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
        family_table_name = f'{schema_name}.{family.name}'
        create_table_statement = CreateTableAs(family_table_name, create_table_query)
        db.session.execute(create_table_statement)

        # TODO: create an index on the id column

    # Set permissions on readonly user to the schema contents
    db.session.execute(GrantUsageOnSchema(schema_name, 'db_ro_user'))


def _update_global_json_views(schema_name):
    logger.info('Updating global json views')

    # Create postgres schema
    db.session.execute(DropSchemaIfExists(schema_name, cascade=True))
    db.session.execute(CreateSchema(schema_name))

    # Get all the known families
    families = Family.query.filter(Family.fk_workspace_id.is_(None)).distinct(Family.name)
    # This is the metadata entries related to the latest global families
    global_metadata = Metadata.get_latest_global()
    # Extract metadata per family
    master_query = _make_json_view_query(global_metadata, families)

    family_table_name = f'{schema_name}.metadata'
    create_table_statement = CreateTableAs(family_table_name, master_query)
    db.session.execute(create_table_statement)

    # TODO: create an index on the id column

    # Set permissions on readonly user to the schema contents
    db.session.execute(GrantUsageOnSchema(schema_name, 'db_ro_user'))
