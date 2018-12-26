import connexion

from app import db
from app.models import Workspace


def fetch():
    """ List workspaces

    Returns
    -------
    list
        List of Workspace details as a dictionaries

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

    return [workspace.to_dict() for workspace in query_set.all()]


def create(*, body):
    """ Create a new workspace

    Returns
    -------
    dict
        Workspace details
    """
    workspace = Workspace(
        name=body['name'],
        temporary=body.get('temporary', False),
        description=body['description'],
    )
    db.session.add(workspace)
    db.session.commit()
    return workspace.to_dict()
