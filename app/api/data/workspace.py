import logging
from requests import codes

from connexion import request
from kombu.exceptions import OperationalError
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Family, Workspace, WorkspaceState
from app.api.exceptions import APIException
from app.helpers.celery import log_task
from app.api.data.tasks import init_workspace, init_data_bucket, \
    wait_for_workspace, commit_workspace, delete_workspace, scan_workspace
from app.api.exceptions import InvalidTransitionException

logger = logging.getLogger(__name__)


# TODO: remove this explanation when werkzeug >=0.15 is released
# NOTE: On several places here, we are using the 412 (precondition failed)
# status code. Flask uses werkzeug to serve the requests. Werkzeug-0.14 has a
# bug where the responses that have this code are sent without body.
# This bug is documented in https://github.com/pallets/werkzeug/issues/1231
# and fixed in the PR https://github.com/pallets/werkzeug/pull/1255
# However, this has not been released yet.


def fetch(*, user, token_info=None):  # TODO: this is how to get the user, but is this what we want?
    """ List workspaces

    Returns
    -------
    list
        List of Workspace details as a dictionaries
    int
        HTTP response code

    """
    # Filtering
    query_args = request.args
    query_set = Workspace.query

    if 'name' in query_args:
        name = query_args['name']
        query_set = query_set.filter_by(name=name)

    if 'owner' in query_args:
        raise NotImplementedError

    if 'deleted' in query_args:
        raise NotImplementedError

    # TODO: provide an order_by on the query parameters
    query_set = query_set.order_by(Workspace.id.desc())

    return [workspace.to_dict() for workspace in query_set.all()], codes.ok


def create(*, body, user, token_info=None):
    """ Create a new workspace

    Returns
    -------
    dict
        Workspace details

    int
        HTTP response code
    """
    logger.info('Attempting to create workspace from %s', body)

    # Create workspace on the database
    workspace = Workspace(
        name=body['name'],
        description=body['description'],
        temporary=body.get('temporary', False),
        owner=user,
    )
    workspace.state = WorkspaceState.INITIALIZING
    db.session.add(workspace)

    # Verify contraints and generate the workspace id that will be needed for
    # the next part of the family initialization
    try:
        db.session.flush()
    except IntegrityError as exc:
        logger.info('Workspace creation denied due to repeated user and name')
        logger.debug('Workspace creation error details:', exc_info=exc)
        raise APIException(status=codes.bad_request,
                           title='Invalid workspace name',
                           detail='Workspace name already exists for user')

    # Create temporary families that will be correctly initialized later.
    # By default, the base family must be present. If not present, set it to
    # the latest version
    families = body['families']
    if 'base' not in families:
        families['base'] = None
    for name, version in families.items():
        family = Family(name=name,
                        version=version,
                        description='No description provided',
                        fk_workspace_id=workspace.id)
        logger.info('Adding family %s version %s to workspace %s',
                    family, family.version, family.fk_workspace_id)
        db.session.add(family)

    # Schedule the initialization tasks.
    # Note that there is an egg and chicken problem here: we need to initialize
    # the workspace in the database but also schedule a task. Both of these
    # operations can fail or take time. Here, we arbitrarily decided to schedule
    # the task with some delay (countdown=1 sec) then commit the database.
    # For this reason, the first part of the chain of task is to wait for the
    # workspace to be exist in the database (after db.session.commit()).
    try:
        chain = (
            # Wait for the workspace to be added to the database
            wait_for_workspace.si(workspace.id) |
            # Initialize its families
            init_workspace.si(workspace.id) |
            # Initialize its resources
            init_data_bucket.si(workspace.id)
        )
        background_task = chain.apply_async(countdown=1)
        # Log the celery chain in order
        log_task(background_task)

    except OperationalError as exc:
        logger.error('Failed to schedule workspace creation task', exc_info=exc)
        raise APIException(status=codes.service_unavailable,
                           title='Service unavailable',
                           detail='Could not initialize workspace due to a '
                                  'temporary backend error. '
                                  'The administrator has been notified.')

    # Save database with families and workspace modifications
    db.session.commit()

    # Respond with the workspace details
    return workspace.to_dict(), codes.created


def details(*, wid):
    """ Get workspace details by id

    Parameters
    ----------
    wid: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.get_or_404(wid)
    return workspace.to_dict(), codes.ok


def delete(*, wid):
    """ Request deletion of a workspace by id

    Parameters
    ----------
    wid: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.get_or_404(wid)

    # update workspace state, which will fail if it is not a valid transition
    try:
        workspace.state = WorkspaceState.DELETING
        db.session.add(workspace)
    except InvalidTransitionException as ex:
        # See note on 412 code and werkzeug on top of this file
        logger.info(ex, exc_info=ex)
        raise APIException(status=codes.precondition_failed,
                           title=f'Workspace cannot be deleted',
                           detail=f'Cannot delete a workspace on {workspace.state.name} state')

    # Update database before sending the async task
    db.session.commit()

    # Schedule the deletion task
    background_task = (
        delete_workspace.si(workspace.id)
    ).apply_async()

    # Log the celery chain in order
    log_task(background_task)

    return workspace.to_dict(), codes.accepted


def commit(*, wid):
    """ Request commit of all metadata and files of a workspace

    Parameters
    ----------
    wid: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.get_or_404(wid)

    # update workspace state, which will fail if it is not a valid transition
    try:
        workspace.state = WorkspaceState.COMMITTING
        db.session.add(workspace)
    except InvalidTransitionException as ex:
        # See note on 412 code and werkzeug on top of this file
        logger.info(ex, exc_info=ex)
        raise APIException(status=codes.precondition_failed,
                           title=f'Workspace cannot be committed',
                           detail=f'Cannot commit a workspace on {workspace.state.name} state')

    # Update database before sending the async task
    db.session.commit()

    # Schedule the scanning task
    background_task = (
        commit_workspace.si(workspace.id)
    ).apply_async()

    # Log the celery chain in order
    log_task(background_task)

    return workspace.to_dict(), codes.accepted


def scan(*, wid):
    """ Request an update of the views of a workspace

    Parameters
    ----------
    wid: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.get_or_404(wid)

    # update workspace state, which will fail if it is not a valid transition
    try:
        workspace.state = WorkspaceState.SCANNING
    except InvalidTransitionException as ex:
        # See note on 412 code and werkzeug on top of this file
        logger.info(ex, exc_info=ex)
        raise APIException(status=codes.precondition_failed,
                           title=f'Workspace cannot be scanned',
                           detail=f'Cannot scan a workspace on {workspace.state.name} state')

    # Update database before sending the async task
    db.session.commit()

    # Schedule the scanning task
    background_task = (
        scan_workspace.si(workspace.id)
    ).apply_async()

    # Log the celery chain in order
    log_task(background_task)

    return workspace.to_dict(), codes.accepted


def query(*, wid, user, token_info=None, **kwargs):
    workspace = Workspace.get_or_404(wid)

    # TODO: verify workspace state

    logger.info('Querying %s as %s', wid, kwargs)

    schema_name = workspace.pg_schema_name
    if schema_name is None:
        raise APIException(status=codes.precondition_failed,
                           title='Workspace cannot be queried',
                           detail=f'Cannot query a workspace that has not been scanned')

    return [{'id': 123}, {'id': 456}], codes.ok
