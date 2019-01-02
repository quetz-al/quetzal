import io
import logging
from requests import codes
from uuid import uuid4

from connexion import NoContent, problem, request
from flask import send_file, current_app
from sqlalchemy import func

from app import db
from app.models import Metadata, Family, Workspace, WorkspaceState
from app.api.data.tasks import init_workspace, delete_workspace, scan_workspace
from app.api.data.helpers import get_client, get_bucket, get_data_bucket


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
    # Create workspace on the database
    workspace = Workspace(
        name=body['name'],
        description=body['description'],
        temporary=body.get('temporary', False),
        user_id=user.id,
    )
    db.session.add(workspace)

    # Create or retrieve families
    queryset = (Family.query
                .filter_by(workspace=None)
                .distinct(Family.name, Family.version)
                .order_by(Family.name, Family.version.desc())
    )
    # By default, the base family must be present
    families = body['families']
    if 'base' not in families:
        families['base'] = None

    for name, version in families.items():
        logger.info('Adding family %s at version %s', name, version)
        family = Family(name=name, description='No description')
        family.workspace_id = workspace.id

        if version is None:
            # Determine the latest family
            latest = queryset.filter_by(name=name).first()
            if latest is None:
                family.version = 0
            else:
                family.version = latest.version
        else:
            # Use an existing family
            existing = queryset.filter_by(name=name, version=version).first()
            if existing is None:
                raise Exception(f'Family {name} does not have version {version}')
            family.description = existing.description

        db.session.add(family)

    db.session.commit()

    # Schedule the initialization task
    init_workspace.delay(workspace.id)

    # Respond with the workspace details
    return workspace.to_dict(), codes.created


def details(*, id):
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


def delete(*, id):
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


def commit(*, id):
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


def scan(*, id):
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


def files(*, id):
    raise NotImplementedError


def add_file(*, id, body):

    logger.info('add_file %s %s %d', id, type(body), len(body), exc_info=True)

    workspace = Workspace.query.get(id)
    if workspace is None:
        # TODO: raise exception, when errors are managed correctly
        return problem(codes.not_found, 'Not found',
                       f'Workspace {id} does not exist')

    # Get the base metadata family or create it if not present
    # ... aha this seems not trivial ...
    # base_family = Metadata.get_instance_by_workspace(...) # for a lack of a better name


    # Add basic metadata
    file_id = uuid4()
    base_metadata = {
        'id': str(file_id),
        'filename': str(file_id),
        'path': '',
        'size': len(body),
        'checksum': '',
        'url': '',
    }

    # Send file to bucket
    client = get_client()
    data_bucket = get_data_bucket(client)
    blob = data_bucket.blob(str(file_id))
    file_io = io.BytesIO(body)
    blob.upload_from_file(file_io, rewind=True)
    base_metadata['url'] = f'gs://{data_bucket.name}/{file_id}'

    # Save model

    return {}, codes.created


def update_metadata(*, id, uuid, body):
    print(id, uuid, body)
    return {}, codes.ok


def fetch_file(*, uuid):
    return fetch_workspace_file(id=None, uuid=uuid)


def fetch_workspace_file(*, id=None, uuid):
    # Content negotiation
    best = request.accept_mimetypes.best_match(['application/json',
                                                'application/octet-stream'])
    if best == 'application/json':
        return {'fake': 'metadata'}, codes.ok

    elif best == 'application/octet-stream':
        from tempfile import NamedTemporaryFile
        temp = NamedTemporaryFile('w')
        temp.write('hello world\n')
        temp.flush()
        response = send_file(open(temp.name),
                             mimetype='application/octet-stream')
        response.direct_passthrough = False
        return response, codes.ok

    return problem(codes.bad_request,
                   'Invalid accept header',
                   f'Cannot serve content of type {request.accept_mimetypes}')
