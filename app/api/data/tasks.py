import logging

from app import celery, db
from app.models import Workspace, WorkspaceState


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
    workspace.state = WorkspaceState.READY
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
