import logging
from typing import Mapping, Tuple

from connexion import request
from kombu.exceptions import OperationalError
from requests import codes
from sqlalchemy.exc import IntegrityError

from quetzal.app import db
from quetzal.app.api.data.tasks import (
    init_workspace, init_data_bucket,
    wait_for_workspace, commit_workspace, delete_workspace, scan_workspace
)
from quetzal.app.api.exceptions import APIException, InvalidTransitionException
from quetzal.app.models import Family, User, Workspace, WorkspaceState
from quetzal.app.helpers.celery import log_task
from quetzal.app.helpers.pagination import paginate
from quetzal.app.security import (
    PublicReadPermission, PublicWritePermission,
    WriteWorkspacePermission, CommitWorkspacePermission
)


logger = logging.getLogger(__name__)


FAMILY_NAME_BLACKLIST = ('id', )


def fetch(*, user: User) -> Tuple[Mapping, int]:
    """ List workspaces

    Returns
    -------
    list
        List of Workspace details as a dictionaries
    int
        HTTP response code

    """

    if not PublicReadPermission.can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to list workspaces')

    # Filtering
    query_args = request.args
    query_set = Workspace.query

    if 'name' in query_args:
        name = query_args['name']
        query_set = query_set.filter_by(name=name)

    if 'owner' in query_args:
        query_set = query_set.join(User).filter(User.username == query_args['owner'])

    if 'deleted' in query_args and query_args['deleted']:
        # query_set already has the deleted workspaces
        pass
    else:
        # by default, don't list the deleted workspaces
        query_set = query_set.filter(Workspace._state != WorkspaceState.DELETED)

    # TODO: provide an order_by on the query parameters
    # TODO: consider permissions here and how it plays with owner in query_args
    query_set = query_set.order_by(Workspace.id.desc())

    pager = paginate(query_set, serializer=Workspace.to_dict)
    return pager.response_object(), codes.ok


def create(*, body: Mapping, user: User, **kwargs) -> Tuple[Mapping, int]:
    """ Create a new workspace

    Returns
    -------
    dict
        Workspace details

    int
        HTTP response code
    """
    if not PublicWritePermission.can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to create workspaces')

    logger.info('Attempting to create workspace from %s', body)

    # Create workspace on the database
    name = body['name']
    username = user.username
    workspace = Workspace(
        name=name,
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
                           detail=f'A workspace named "{name}" already exists for user "{username}"')

    # Create temporary families that will be correctly initialized later.
    # By default, the base family must be present. If not present, set it to
    # the latest version
    families = body['families']
    if 'base' not in families:
        families['base'] = None
    for name, version in families.items():
        if name in FAMILY_NAME_BLACKLIST:
            raise APIException(status=codes.bad_request,
                               title='Invalid family name',
                               detail=f'Family name "{name}" is not permitted')
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


def details(*, wid: int) -> Tuple[Mapping, int]:
    """ Get workspace details by id

    Parameters
    ----------
    wid
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.get_or_404(wid)

    # TODO: consider read permission of workspaces
    # if not ReadWorkspacePermission(wid).can():
    #     raise APIException(status=codes.forbidden,
    #                        title='Forbidden',
    #                        detail='You are not authorized to read this workspace')

    return workspace.to_dict(), codes.ok


def delete(*, wid: int) -> Tuple[Mapping, int]:
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

    if not WriteWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to delete this workspace')

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


def commit(*, wid: int) -> Tuple[Mapping, int]:
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

    if not CommitWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to commit this workspace')

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


def scan(*, wid: int) -> Tuple[Mapping, int]:
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

    if not WriteWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to scan this workspace')

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
