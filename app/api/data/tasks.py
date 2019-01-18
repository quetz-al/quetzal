import logging

from app import celery, db
from app.models import Workspace, WorkspaceState, Metadata, Family
from app.api.exceptions import WorkerException
from app.api.data.helpers import get_client, get_bucket


logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=10)
def wait_for_workspace(self, id):
    """ Wait until a workspace is created on the database

    Parameters
    ----------
    id: int
        Workspace identifier

    Returns
    -------

    """
    logger.info('Waiting for creation of workspace %s ...', id)

    workspace = Workspace.query.get(id)
    if workspace is None:
        logger.info('Workspace is not available yet')
        raise self.retry(countdown=1)

    logger.info('Workspace %s is now available', id)


@celery.task()
def init_workspace(id):
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
    id: int
        Workspace identifier

    Returns
    -------
    None

    """
    logger.info('Initializing workspace %s...', id)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(id)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.INITIALIZING:
        raise WorkerException('Workspace was not on the expected state')

    # Determine the most recent "global" metadata entry so that the workspace
    # has a reference number from which any new metadata will be ignored
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
def init_data_bucket(id):
    logger.info('Initializing bucket of workspace %s...', id)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(id)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.INITIALIZING:
        raise WorkerException('Workspace was not on the expected state')

    # Do the initialization task
    # TODO: manage exceptions/errors
    # TODO: manage location and storage class through configuration or workspace options
    bucket_name = f'quetzal-ws-{workspace.id}-{workspace.owner.username}-{workspace.name}'
    client = get_client()
    bucket = client.bucket(bucket_name)
    bucket.storage_class = 'REGIONAL'
    bucket.create(client=client, location='europe-west1')

    # Update the database model
    workspace.state = WorkspaceState.READY
    workspace.data_url = f'gs://{bucket_name}'
    db.session.add(workspace)
    db.session.commit()


@celery.task()
def delete_workspace(id):
    logger.info('Deleting workspace %s...', id)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(id)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.DELETING:
        raise WorkerException('Workspace was not on the expected state')

    # Do the deletion task
    # TODO: manage exceptions/errors
    bucket = get_bucket(workspace.data_url)

    # Delete all blobs first
    blobs = list(bucket.list_blobs())
    bucket.delete_blobs(blobs)

    # Delete the bucket
    bucket.delete()

    # Update the database model
    workspace.state = WorkspaceState.DELETED
    db.session.add(workspace)
    db.session.commit()


@celery.task()
def scan_workspace(id):
    logger.info('Scanning workspace %s...', id)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(id)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.SCANNING:
        raise WorkerException('Workspace was not on the expected state')

    # Do the scanning task
    import time; time.sleep(5)
    workspace.state = WorkspaceState.READY
    db.session.add(workspace)
    db.session.commit()


@celery.task()
def commit_workspace(id):
    logger.info('Committing workspace %s...', id)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(id)
    if workspace is None:
        raise WorkerException('Workspace was not found')

    if workspace.state != WorkspaceState.COMMITTING:
        raise WorkerException('Workspace was not on the expected state')

    # Do the committing task
    import time; time.sleep(5)
    workspace.state = WorkspaceState.READY
    db.session.add(workspace)
    db.session.commit()
