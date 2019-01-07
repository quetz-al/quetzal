import io
from uuid import uuid4

from connexion import problem
from flask import request, send_file
from requests import codes

from app import db
from app.api.data.helpers import get_data_bucket, md5
from app.api.data.workspace import logger
from app.models import Workspace, Metadata, Family


def create(*, id, body):

    logger.info('create %s %s %d', id, type(body), len(body), exc_info=True)

    workspace = Workspace.query.get(id)
    if workspace is None:
        # TODO: raise exception, when errors are managed correctly
        return problem(codes.not_found, 'Not found',
                       f'Workspace {id} does not exist')

    # Get the base metadata family in order to put the basic metadata info
    base_family = workspace.families.filter_by(name='base').first()

    # Add basic metadata
    meta = Metadata(id_file=uuid4(), family=base_family)
    meta.json = {
        'id': str(meta.id_file),
        'filename': str(meta.id_file),
        'path': '',
        'size': len(body),
        'checksum': md5(body),
        'url': '',
    }
    db.session.add(meta)

    # Send file to bucket
    data_bucket = get_data_bucket()
    blob = data_bucket.blob(str(meta.id_file))
    file_io = io.BytesIO(body)
    blob.upload_from_file(file_io, rewind=True)
    meta.json['url'] = f'gs://{data_bucket.name}/{meta.id_file}'

    # Save model
    db.session.commit()

    return meta.to_dict(), codes.created


def update_metadata(*, id, uuid, body):
    # TODO: maybe change spec to {"metadata": object}

    workspace = Workspace.query.get(id)
    if workspace is None:
        # TODO: raise exception, when errors are managed correctly
        return problem(codes.not_found, 'Not found',
                       f'Workspace {id} does not exist')

    # Before changing/updating the matadata, we must ensure that the changes
    # are valid. That is:
    # * Metadata of the "base" family cannot be modified, with the exception of
    #   the "path" entry
    # * The "id" entry cannot be changed for any family
    # * The family must have been declared on the creation of the workspace
    for name, content in body.items():
        # Verification: base metadata
        if name == 'base' and content.keys() != {'path'}:
            return problem(codes.bad_request,  # see RFC 7231 or https://stackoverflow.com/a/3290198/227103
                           'Invalid metadata modification',
                           'Cannot change metadata family "base" for the exception of its path')

        # Verification: id cannot be changed
        if 'id' in content.keys():
            return problem(codes.bad_request,
                           'Invalid metadata modification',
                           'Cannot change metadata "id" entry')

        # Family exists on this workspace?
        family = workspace.families.filter_by(name=name).first()
        if family is None:
            return problem(codes.bad_request,
                           'Invalid family',
                           f'Workspace does not have family {name}')

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
            workspace = Workspace.query.get(id)
            if workspace is None:
                # TODO: raise exception, when errors are managed correctly
                return problem(codes.not_found, 'Not found',
                               f'Workspace {id} does not exist')

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

    return problem(codes.bad_request,
                   'Invalid accept header',
                   f'Cannot serve content of type {request.accept_mimetypes}')


def fetch(*, id):
    raise NotImplementedError


def _all_metadata(file_id, workspace):
    meta = {}
    for family in workspace.families.all():
        latest = Metadata.get_latest(file_id, family)
        if latest is not None:
            meta[family.name] = latest.json
    return meta
