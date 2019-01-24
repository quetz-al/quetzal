import os
from uuid import uuid4

from flask import request, send_file
from requests import codes

from app import db
from app.api.data.helpers import get_data_bucket, get_readable_info, split_check_path
from app.api.data.workspace import logger
from app.api.exceptions import APIException
from app.models import Workspace, Metadata


def create(*, id, file_content, user, token_info=None):
    workspace = Workspace.get_or_404(id)

    # Creating a file requires new metadata, so the check here is to verify
    # that the workspace status permits changes on metadata
    if not workspace.can_change_metadata:
        # See note on 412 code and werkzeug on top of workspace.py file
        raise APIException(status=codes.precondition_failed,
                           title='Cannot add file to workspace',
                           detail=f'Cannot add files to a workspace on {workspace.state.name} state')

    # Get the base metadata family in order to put the basic metadata info.
    base_family = workspace.families.filter_by(name='base').first()

    # This query should not be None because all workspaces have a 'base' family,
    # but in case this happens, it would be a problem of the current
    # implementation (possibly by manually doing things like in unit tests).
    # Just in case, we will raise an exception
    if base_family is None:
        logger.error('Workspace %d does not have base family metadata!',
                     workspace.id)
        raise APIException(status=codes.server_error,
                           title='Incorrect workspace configuration',
                           detail='Cannot add files to workspace because it does '
                                  'not have the "base" family. This situation '
                                  'should not happen and will be reported to '
                                  'the administrator')

    #  Create metadata object
    meta = Metadata(id_file=uuid4(), family=base_family)
    md5, size = get_readable_info(file_content)
    path, filename = split_check_path(file_content.filename)
    meta.json = {
        'id': str(meta.id_file),
        'filename': filename,
        'path': path,
        'size': size,
        'checksum': md5,
        'url': '',
    }
    db.session.add(meta)

    # TODO: write a wrapper to the file object in order to send the file and get the md5 and size
    # (everything at the same time instead of doing a two-pass read)

    # Send file to bucket
    meta.json['url'] = _upload_file(str(meta.id_file), file_content)

    # Save model
    db.session.add(meta)
    db.session.commit()

    return meta.to_dict(), codes.created


def _upload_file(name, content):
    """Upload contents to the google data bucket"""
    data_bucket = get_data_bucket()
    blob = data_bucket.blob(name)
    blob.upload_from_file(content, rewind=True)
    return f'gs://{data_bucket.name}/{name}'


def update_metadata(*, id, uuid, body):
    # TODO: maybe change spec to {"metadata": object}

    workspace = Workspace.get_or_404(id)

    if not workspace.can_change_metadata:
        # See note on 412 code and werkzeug on top of workspace.py file
        raise APIException(status=codes.precondition_failed,
                           title=f'Cannot update metadata of file',
                           detail=f'Cannot update metadata of files to a '
                                  f'workspace on {workspace.state.name} state')

    # Before changing/updating the matadata, we must ensure that the changes
    # are valid. That is:
    # * Metadata of the "base" family cannot be modified, with the exception of
    #   the "path" entry
    # * The "id" entry cannot be changed for any family
    # * The family must have been declared on the creation of the workspace
    for name, content in body.items():
        # Verification: base metadata
        if name == 'base' and content.keys() != {'path'}:
            raise APIException(status=codes.bad_request,  # see RFC 7231 or https://stackoverflow.com/a/3290198/227103
                               title='Invalid metadata modification',
                               detail='Cannot change metadata family "base" for the exception of its path')

        # Verification: id cannot be changed
        if 'id' in content.keys():
            raise APIException(status=codes.bad_request,
                               title='Invalid metadata modification',
                               detail='Cannot change metadata "id" entry')

        # Family exists on this workspace?
        family = workspace.families.filter_by(name=name).first()
        if family is None:
            raise APIException(status=codes.bad_request,
                               title='Invalid family',
                               detail=f'Workspace does not have family {name}')

        latest = Metadata.get_latest(uuid, family)
        if latest is None:
            # This file has no metadata (local or global) under this particular family
            logger.debug('There is no previous metadata, creating a new metadata entry')
            latest = Metadata(id_file=uuid, family=family, json={'id': uuid})

        elif latest.family.workspace is None:
            # This file has some global (ie committed) metadata
            logger.info('A previous metadata entry exists, copying metadata %s', latest)
            latest = latest.copy()
            latest.family = family
        else:
            # This file has some local (ie not committed) metadata
            logger.info('Got latest %s', latest)

        latest.update(content)
        db.session.add(latest)

    # Query again the latest metadata
    meta = _all_metadata(uuid, workspace)

    # Save changes
    db.session.commit()

    return meta, codes.ok


def set_metadata(*, id, uuid, body):
    # TODO: maybe change spec to {"metadata": object}
    workspace = Workspace.get_or_404(id)

    if not workspace.can_change_metadata:
        # See note on 412 code and werkzeug on top of workspace.py file
        raise APIException(status=codes.precondition_failed,
                           title=f'Cannot change metadata of file',
                           detail=f'Cannot change metadata of files to a '
                                  f'workspace on {workspace.state.name} state')

    raise NotImplementedError


def details(*, uuid):
    return details_w(id=None, uuid=uuid)


def details_w(*, id=None, uuid):
    # Content negotiation
    best = request.accept_mimetypes.best_match(['application/json',
                                                'application/octet-stream'],
                                               default=None)
    if best == 'application/json':
        # When there is a workspace, give its workspace
        # Otherwise, give the latest metadata
        if id is not None:
            workspace = Workspace.get_or_404(id)

            meta = _all_metadata(uuid, workspace)
            return {'id': uuid, 'metadata': meta}, codes.ok

        raise NotImplementedError('metadata without workspace not implemented yet')

    elif best == 'application/octet-stream':
        from tempfile import NamedTemporaryFile
        temp = NamedTemporaryFile('w')
        temp.write('hello world\n')
        temp.flush()
        response = send_file(open(temp.name),
                             mimetype='application/octet-stream')
        response.direct_passthrough = False
        return response, codes.ok

    raise APIException(status=codes.bad_request,
                       title='Invalid accept header',
                       detail=f'Cannot serve content of type {request.accept_mimetypes}')


def fetch(*, id):
    raise NotImplementedError


def _all_metadata(file_id, workspace):
    meta = {}
    for family in workspace.families.all():
        latest = Metadata.get_latest(file_id, family)
        if latest is not None:
            meta[family.name] = latest.json
    return meta
