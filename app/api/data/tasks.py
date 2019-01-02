import logging

from app import celery, db
from app.models import Workspace, WorkspaceState
from app.api.data.helpers import get_client, get_bucket


logger = logging.getLogger(__name__)


@celery.task()
def init_workspace(id):
    logger.info('Initializing workspace %s...', id)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(id)
    if workspace is None:
        raise Exception('Workspace was not found')

    if workspace.state != WorkspaceState.INITIALIZING:
        raise Exception('Workspace was not on the expected state')

    # Do the initialization task
    # TODO: manage exceptions/errors
    bucket_name = f'quetzal-ws-{workspace.owner.username}-{workspace.name}'
    client = get_client()
    bucket = client.bucket(bucket_name)
    bucket.storage_class = 'REGIONAL'
    bucket.location = 'europe-west1'
    bucket.create()

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
        raise Exception('Workspace was not found')

    if workspace.state != WorkspaceState.PROCESSING:  # TODO: maybe more states are possible here
        raise Exception('Workspace was not on the expected state')

    # Do the deletion task
    # TODO: manage exceptions/errors
    client = get_client()
    bucket = get_bucket(client, workspace.data_url)

    # Delete all blobs first
    blobs = list(bucket.list_blobs())
    bucket.delete_blobs(blobs)

    # Delete the bucket
    bucket.delete()

    # Update the database model
    db.session.delete(workspace)
    db.session.commit()


@celery.task()
def scan_workspace(id):
    logger.info('Scanning workspace %s...', id)

    # Get the workspace object and verify preconditions
    workspace = Workspace.query.get(id)
    if workspace is None:
        raise Exception('Workspace was not found')

    if workspace.state != WorkspaceState.PROCESSING:
        raise Exception('Workspace was not on the expected state')

    # Do the scanning task
    import time; time.sleep(5)
    workspace.state = WorkspaceState.READY
    db.session.commit()
