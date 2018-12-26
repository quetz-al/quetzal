from requests import codes

import connexion
from connexion import NoContent, problem

from app import db
from app.models import Workspace


def fetch():
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
    workspace = Workspace(
        name=body['name'],
        temporary=body.get('temporary', False),
        description=body['description'],
    )
    db.session.add(workspace)
    db.session.commit()
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
    return workspace.to_dict(), codes.accepted
