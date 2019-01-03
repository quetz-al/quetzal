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
    file_metas = (
        db.session.query(Metadata)
        .join(Family)
        .filter_by(workspace=workspace)
        .filter(Metadata.id_file == uuid)
    )
    for name, content in body.items():
        if name == 'base' and content.keys() != {'path'}:
            return problem(codes.bad_request,  # see RFC 7231 or https://stackoverflow.com/a/3290198/227103
                           'Invalid metadata modification',
                           'Cannot change metadata family "base" for the exception of its path')
        if 'id' in content.keys():
            return problem(codes.bad_request,
                           'Invalid metadata modification',
                           'Cannot change metadata "id" entry')
        # TODO: verify no changes on id
        # TODO: verify no changes on base
        previous = file_metas.filter_by(name=name).first()
        if previous is not None:
            previous.json.update(content)

        # TODO: continue here, db.session.add, commit etc

    return {}, codes.ok


def details(*, uuid):
    return details_w(id=None, uuid=uuid)


def details_w(*, id=None, uuid):
    # Content negotiation
    best = request.accept_mimetypes.best_match(['application/json',
                                                'application/octet-stream'])
    if best == 'application/json':
        # When there is a workspace, give its workspace
        # Otherwise, give the latest metadata
        if id is not None:
            workspace = Workspace.query.get(id)
            file_metas = (
                db.session.query(Metadata)
                .join(Family)
                .filter_by(workspace=workspace)
                .filter(Metadata.id_file == uuid)
            )
            # TODO: add request of metadata that has not been modified yet
            meta = {
                'id': uuid,
                'metadata': {m.family.name: m.json for m in file_metas},
            }
            return meta, codes.ok

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


def fetch(*, id):
    raise NotImplementedError
