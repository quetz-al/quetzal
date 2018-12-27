from requests import codes

import connexion
from connexion import NoContent, problem

from app import db
from app.models import Workspace, WorkspaceState
from app.api.data.tasks import init_workspace, delete_workspace, scan_workspace


# TODO: remove this explanation when werkzeug >=0.15 is released
# NOTE: On several places here, we are using the 412 (precondition failed)
# status code. Flask uses werkzeug to serve the requests. Werkzeug-0.14 has a
# bug where the responses that have this code are sent without body.
# This bug is documented in https://github.com/pallets/werkzeug/issues/1231
# and fixed in the PR https://github.com/pallets/werkzeug/pull/1255
# However, this has not been released yet.


def fetch(*, user=None, token_info=None):  # TODO: this is how to get the user, but is this what we want?
    """ List workspaces

    Returns
    -------
    list
        List of Workspace details as a dictionaries
    int
        HTTP response code

    """
    # Filtering
    query_args = connexion.request.args
    query_set = Workspace.query

    if 'name' in query_args:
        name = query_args['name']
        query_set = query_set.filter_by(name=name)

    if 'owner' in query_args:
        raise NotImplementedError

    if 'deleted' in query_args:
        raise NotImplementedError

    return [workspace.to_dict() for workspace in query_set.all()], codes.ok


def create(*, body):
    """ Create a new workspace

    Returns
    -------
    dict
        Workspace details

    int
        HTTP response code
    """
    # Create workspace on the database
    workspace = Workspace(
        name=body['name'],
        description=body['description'],
        temporary=body.get('temporary', False),
    )
    db.session.add(workspace)
    db.session.commit()

    # Schedule the initialization task
    init_workspace.delay(workspace.id)

    # Respond with the workspace details
    return workspace.to_dict(), codes.created


def details(id):
    """ Get workspace details by id

    Parameters
    ----------
    id: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.query.get(id)
    if workspace is None:
        # TODO: raise exception, when errors are managed correctly
        return NoContent, codes.not_found
    return workspace.to_dict(), codes.ok


def delete(id):
    """ Request deletion of a workspace by id

    Parameters
    ----------
    id: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.query.get(id)
    if workspace is None:
        # TODO: raise exception, when errors are managed correctly
        return problem(codes.not_found, 'Not found',
                       f'Workspace {id} does not exist')

    # check preconditions
    if workspace.state != WorkspaceState.READY:
        # See note on 412 code and werkzeug on top of this file
        return problem(codes.precondition_failed,
                       'Workspace cannot be deleted',
                       f'Cannot delete a workspace on {workspace.state.name} state, '
                       f'it must be on the {WorkspaceState.READY.name} state')

    # Mark workspace as processing and save to database
    workspace.state = WorkspaceState.PROCESSING
    db.session.add(workspace)
    db.session.commit()

    # Schedule the deletion task
    delete_workspace.delay(workspace.id)

    return workspace.to_dict(), codes.accepted


def commit(id):
    """ Request commit of all metadata and files of a workspace

    Parameters
    ----------
    id: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.query.get(id)
    if workspace is None:
        # TODO: raise exception, when errors are managed correctly
        return problem(codes.not_found, 'Not found',
                       f'Workspace {id} does not exist')
    return workspace.to_dict(), codes.accepted


def scan(id):
    """ Request an update of the views of a workspace

    Parameters
    ----------
    id: int
        Workspace identifier

    Returns
    -------
    dict
        Workspace details
    int
        HTTP response code

    """
    workspace = Workspace.query.get(id)
    if workspace is None:
        # TODO: raise exception, when errors are managed correctly
        return problem(codes.not_found, 'Not found',
                       f'Workspace {id} does not exist')

    # Schedule the scanning task
    scan_workspace.delay(workspace.id)

    return workspace.to_dict(), codes.accepted
