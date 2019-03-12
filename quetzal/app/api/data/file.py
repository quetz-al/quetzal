import datetime
import logging
import os
import pathlib
import tempfile
import urllib.parse
from uuid import uuid4

from flask import current_app, request, send_file
from requests import codes

from quetzal.app import db
from quetzal.app.helpers.google_api import get_object, get_data_bucket
from quetzal.app.helpers.files import split_check_path, get_readable_info
from quetzal.app.helpers.pagination import paginate
from quetzal.app.api.exceptions import APIException
from quetzal.app.models import BaseMetadataKeys, Family, Workspace, Metadata
from quetzal.app.security import (
    PublicReadPermission, ReadWorkspacePermission, WriteWorkspacePermission
)


logger = logging.getLogger(__name__)


def create(*, wid, content=None, user, token_info=None):
    workspace = Workspace.get_or_404(wid)

    if content is None:
        raise APIException(status=codes.bad_request,
                           title='Missing file content',
                           detail='Cannot create a file without contents')

    if not WriteWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to add files to this workspace')

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
    md5, size = get_readable_info(content)
    path, filename = split_check_path(content.filename)
    meta.json = {
        'id': str(meta.id_file),
        'filename': filename,
        'path': path,
        'size': size,
        'checksum': md5,
        'date': _now(),
        'url': '',
    }
    db.session.add(meta)

    # Send file to bucket
    meta.json['url'] = _upload_file(str(meta.id_file), content)

    # Save model
    db.session.add(meta)
    db.session.commit()

    return meta.json, codes.created


def update_metadata(*, wid, uuid, body):
    workspace = Workspace.get_or_404(wid)

    if not WriteWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to modify metadata on this workspace')

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
    for name, content in body['metadata'].items():
        # Verification: base metadata
        if name == 'base':
            if content.keys() - {'path', 'filename'}:
                # see RFC 7231 or https://stackoverflow.com/a/3290198/227103
                raise APIException(status=codes.bad_request,
                                   title='Invalid metadata modification',
                                   detail='Cannot change metadata family "base" for the exception of its path')
            # Do some verifications on the filename and path
            _verify_filename_path(content.get('filename', ''), content.get('path', ''))

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

    # MetadataQuery again the latest metadata
    meta = _all_metadata(uuid, workspace)

    # Save changes
    db.session.commit()

    return {"id": uuid, "metadata": meta}, codes.ok


def set_metadata(*, wid, uuid, body):
    # TODO: maybe change spec to {"metadata": object}
    workspace = Workspace.get_or_404(wid)

    if not WriteWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to modify metadata on this workspace')

    if not workspace.can_change_metadata:
        # See note on 412 code and werkzeug on top of workspace.py file
        raise APIException(status=codes.precondition_failed,
                           title=f'Cannot change metadata of file',
                           detail=f'Cannot change metadata of files to a '
                                  f'workspace on {workspace.state.name} state')

    raise NotImplementedError


def details(*, uuid):
    """Get the contents or metadata of a file that has been committed"""

    if not PublicReadPermission.can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to read metadata')

    # Content negotiation
    best = request.accept_mimetypes.best_match(['application/json',
                                                'application/octet-stream'],
                                               default=None)
    if best == 'application/json':
        # A request for metadata without workspace means that we should look
        # into metadata that has been committed. That is, it has a null workspace
        # associated to their families
        latest_meta_committed = Metadata.get_latest_global(uuid)

        if not latest_meta_committed:
            raise APIException(status=codes.not_found,
                               title='File not found',
                               detail=f'File {uuid} does not exist or has not '
                                      f'been committed yet.')

        meta = _gather_metadata(latest_meta_committed)
        return {'id': uuid, 'metadata': meta}, codes.ok

    elif best == 'application/octet-stream':
        # A request for content without workspace means that we should look
        # into the "base" metadata that has been committed
        latest_base_meta_committed = Metadata.get_latest_global(uuid, 'base')

        if not latest_base_meta_committed:
            raise APIException(status=codes.not_found,
                               title='File not found',
                               detail=f'File {uuid} does not exist or has not '
                               f'been committed yet.')
        base_meta = latest_base_meta_committed[0]

        tmp_file = _download_file(base_meta.json['url'])
        response = send_file(tmp_file, mimetype='application/octet-stream')
        response.direct_passthrough = False
        return response, codes.ok

    raise APIException(status=codes.bad_request,
                       title='Invalid accept header',
                       detail=f'Cannot serve content of type {request.accept_mimetypes}')


def details_w(*, wid=None, uuid):
    """Get contents or metadata of a file on a workspace"""
    workspace = Workspace.get_or_404(wid)

    if not ReadWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to read metadata on this workspace')

    # Content negotiation
    best = request.accept_mimetypes.best_match(['application/json',
                                                'application/octet-stream'],
                                               default=None)
    if best == 'application/json':
        meta = _all_metadata(uuid, workspace)
        return {'id': uuid, 'metadata': meta}, codes.ok

    elif best == 'application/octet-stream':
        # TODO: continue here! maybe reuse _all_metadata or Metadata.get_latest(...)
        # or create a Workspace.get_base_family()
        base_meta = Metadata.get_latest(uuid, workspace.get_base_family())

        if not base_meta:
            raise APIException(status=codes.not_found,
                               title='File not found',
                               detail=f'File {uuid} does not exist in workspace {wid}')

        tmp_file = _download_file(base_meta.json['url'])
        response = send_file(tmp_file, mimetype='application/octet-stream')
        response.direct_passthrough = False
        return response, codes.ok

    raise APIException(status=codes.bad_request,
                       title='Invalid accept header',
                       detail=f'Cannot serve content of type {request.accept_mimetypes}')


def fetch(*args, **kwargs):
    """Get all the files that have been committed."""
    if not PublicReadPermission.can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to list public files.')

    # Get all the committed base metadata that existed before the creation of
    # the workspace
    previous_meta = (
        Metadata
        .query
        .join(Family)
        .filter(Family.name == 'base',
                # Check that the family's workspace is None: this means is committed
                Family.fk_workspace_id.is_(None))
    )

    # Now take the results but drop repeated entries by file_id,
    # which is possible through a DISTINCT ON combined with an ORDER BY
    union_query = (
        previous_meta
        .distinct(Metadata.id_file)
        .order_by(Metadata.id_file, Metadata.id.desc())
    )

    # Finally, apply filters
    if 'filters' in request.args:
        filters = request.args['filters'].split(',')
        for f in filters:
            try:
                key, value = f.split('=', 1)
            except ValueError:
                raise APIException(status=codes.bad_request,
                                   title='Bad request',
                                   detail='Invalid format for filters.')
            try:
                # Verify that key is a valid value in the enum
                BaseMetadataKeys(key)
            except ValueError:
                raise APIException(status=codes.bad_request,
                                   title='Bad request',
                                   detail=f'"{key}" is not a valid filter key.')
            union_query = union_query.filter(Metadata.json[key].astext == value)

    pager = paginate(union_query, serializer=lambda meta: meta.json)
    return pager.response_object(), 200


def fetch_w(*, wid):
    """Get all the files on a workspace"""
    workspace = Workspace.get_or_404(wid)

    if not ReadWorkspacePermission(wid).can():
        raise APIException(status=codes.forbidden,
                           title='Forbidden',
                           detail='You are not authorized to read metadata on this workspace')

    # Get all the committed base metadata that existed before the creation of
    # the workspace
    previous_meta = (
        Metadata
        .query
        .join(Family)
        .filter(Family.name == 'base',
                # Check that the family's workspace is None: this means is committed
                Family.fk_workspace_id.is_(None),
                # Verify the reference when there is a reference, otherwise it means
                # that there was no metadata before
                Metadata.id <= workspace.fk_last_metadata_id
                if workspace.fk_last_metadata_id is not None else False)
    )

    # Get all the metadata that has been added to this workspace
    workspace_meta = (
        Metadata
        .query
        .join(Family)
        .filter(Family.name == 'base',
                Family.workspace == workspace)
    )

    # Now take the results of both queries, but drop repeated entries by file_id,
    # which is possible through a DISTINCT ON combined with an ORDER BY
    union_query = (
        previous_meta.union(workspace_meta)
        .distinct(Metadata.id_file)
        .order_by(Metadata.id_file, Metadata.id.desc())
    )

    # Finally, apply filters
    if 'filters' in request.args:
        filters = request.args['filters'].split(',')
        for f in filters:
            try:
                key, value = f.split('=', 1)
            except ValueError:
                raise APIException(status=codes.bad_request,
                                   title='Bad request',
                                   detail='Invalid format for filters.')
            try:
                # Verify that key is a valid value in the enum
                BaseMetadataKeys(key)
            except ValueError:
                raise APIException(status=codes.bad_request,
                                   title='Bad request',
                                   detail=f'"{key}" is not a valid filter key.')
            union_query = union_query.filter(Metadata.json[key].astext == value)

    pager = paginate(union_query, serializer=lambda meta: meta.json)
    return pager.response_object(), 200


def _all_metadata(file_id, workspace):
    """Gather all metadata of a file in a workspace

    If a file has metadata of families f1, f2, ..., this function returns
    a dictionary ``{'f1': {...}, 'f2': {...}, ...}``. This structure is suitable
    for the responses of file fetch metadata operations.
    """
    latest_by_family = []
    for family in workspace.families.all():
        latest = Metadata.get_latest(file_id, family)
        if latest is not None:
            latest_by_family.append(latest)
    return _gather_metadata(latest_by_family)


def _gather_metadata(metadatas):
    gathered_meta = {}
    for meta in metadatas:
        gathered_meta[meta.family.name] = meta.json
    return gathered_meta


def _upload_file(name, content):
    storage_backend = current_app.config['QUETZAL_DATA_STORAGE']
    if storage_backend == 'GCP':
        return _upload_file_gcp(name, content)
    elif storage_backend == 'file':
        return _upload_file_local(name, content)
    raise ValueError(f'Unknown storage backend {storage_backend}.')


def _upload_file_gcp(name, content):
    """Upload contents to the google data bucket"""
    data_bucket = get_data_bucket()
    blob = data_bucket.blob(name)
    blob.upload_from_file(content, rewind=True)
    return f'gs://{data_bucket.name}/{name}'


def _upload_file_local(name, content):
    data_dir = pathlib.Path(current_app.config['QUETZAL_FILE_DATA_DIR'])
    target_file = data_dir / name
    with target_file.open('wb') as f:
        f.write(content)
    return f'file://{target_file.resolve()}'


def _download_file(url):
    storage_backend = current_app.config['QUETZAL_DATA_STORAGE']
    if storage_backend == 'GCP':
        return _download_file_gcp(url)
    elif storage_backend == 'file':
        return _download_file_local(url)
    raise ValueError(f'Unknown storage backend {storage_backend}.')


def _download_file_gcp(url):
    # Create a temporal file in memory unless it exceeds 32Mb, whence it
    # will be spilled to a file
    file_obj = tempfile.SpooledTemporaryFile(mode='w+b', max_size=32 * (1 << 20))
    blob = get_object(url)
    blob.download_to_file(file_obj)
    # TODO: manage exception

    file_obj.flush()
    file_obj.seek(0)
    return file_obj


def _download_file_local(url):
    return urllib.parse.urlparse(url).path


def _verify_filename_path(filename, path):
    """Perform some security considerations on filename and path"""
    # TODO: improve this, for the moment this is very limited

    # No unix or windows absolute paths
    if pathlib.PurePosixPath(filename).anchor or pathlib.PureWindowsPath(filename).anchor:
        raise APIException(status=codes.bad_request,
                           title='Invalid filename metadata modification',
                           detail='Filename cannot be an absolute path')
    if pathlib.PurePosixPath(path).anchor or pathlib.PureWindowsPath(path).anchor:
        raise APIException(status=codes.bad_request,
                           title='Invalid path metadata modification',
                           detail='Path cannot be a absolute')

    # No backslashes
    if '\\' in filename or '\\' in path:
        raise APIException(status=codes.bad_request,
                           title='Invalid filename or path modification',
                           detail='Filename and path cannot have backslashes')

    # Filename does not have a path
    if os.path.dirname(filename):
        raise APIException(status=codes.bad_request,
                           title='Invalid filename metadata modification',
                           detail='Filename must not contain a path')

    # Protect path from traversal
    if path:
        current_directory = os.path.abspath(os.curdir)
        requested_path = os.path.relpath(path, start=current_directory)
        requested_path = os.path.abspath(requested_path)
        common_prefix = os.path.commonprefix([requested_path, current_directory])
        if common_prefix != current_directory:
            raise APIException(status=codes.bad_request,
                               title='Invalid path metadata modification',
                               detail='Path contains traversal operation')

        # Path must be normalized
        if os.path.normpath(path) != path:
            raise APIException(status=codes.bad_request,
                               title='Invalid path modification',
                               detail='Path must be normalized')


def _now():
    """Get a datetime object with the current datetime (in UTC) as a string

    This function is also created for ease of unit test mocks
    """
    return str(datetime.datetime.now(datetime.timezone.utc))
