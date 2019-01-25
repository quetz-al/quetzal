import io
import json
import logging
import urllib.parse
from collections import namedtuple

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud.storage import Client

from app.api.data.file import create, details, details_w
from app.api.exceptions import APIException, ObjectNotFoundException
from app.models import Metadata, WorkspaceState


def test_create_file_success(db, db_session, user, make_workspace, file_id, make_file, mocker):
    """File create on success conditions"""
    mocker.patch('app.api.data.file._upload_file', return_value='gs://some_url')
    mocker.patch('app.api.data.file.uuid4', return_value=file_id)

    # Create a workspace with the base family because the file create function
    # assumes the workspace is correctly initialized: it must have a base family
    workspace = make_workspace(families={'base': 0}, owner=user)

    # Create a file with some dummy contents
    content = make_file()
    create(id=workspace.id, file_content=content, user=user)

    # There should be a base metadata entry
    base_family = workspace.families.filter_by(name='base').first()
    base_metadata = Metadata.query.filter_by(id_file=file_id, family=base_family).first()
    assert base_metadata is not None

    # There should be only one new metadata entry
    count = Metadata.query.filter_by(id_file=file_id).count()
    assert count == 1


def test_create_file_missing_base(db, db_session, make_workspace, make_file, user, caplog):
    """Adding a file on a workspace without base family should fail"""
    # Explicitly make a workspace without base family. This should never happen
    # but we want to make sure anyways
    workspace = make_workspace(families={})

    # Create a file with some dummy contents
    content = make_file()
    # caplog.at_level:
    # capture the logger.error log message emitted when the queue fails
    with caplog.at_level(logging.CRITICAL, logger='app.api.data.workspace'):
        with pytest.raises(APIException):
            create(id=workspace.id, file_content=content, user=user)


def test_create_file_correct_metadata(app, db, db_session, make_workspace, file_id, make_file, user, mocker):
    """Creating a file creates the correct metadata"""
    mocker.patch('google.auth.default',
                 return_value=(AnonymousCredentials(), 'mock-project'))
    mocker.patch('app.api.data.helpers.get_client',
                 return_value=Client(project='mock-project'))
    mocker.patch('google.cloud._http.JSONConnection.api_request',
                 return_value={})
    mocker.patch('app.api.data.file.uuid4', return_value=file_id)
    mocker.patch('app.api.data.file._now', return_value='2019-02-03 16:30:11.350719+00:00')
    request_mock = mocker.patch('google.auth.transport.requests.AuthorizedSession.request')

    # A mock function to control external request. Here, there should be a call
    # to create an object in the google cloud bucket
    def authorized_session_request_result(*args, **kwargs):
        result_type = namedtuple('request', ['status_code', 'headers', 'json'])
        return result_type(200,
                           {'location': 'something'},
                           lambda: {})

    request_mock.side_effect = authorized_session_request_result

    # Create a workspace with the base family because the file create function
    # assumes the workspace is correctly initialized: it must have a base family
    workspace = make_workspace(families={'base': 0})

    # Create a file with some dummy contents
    content = make_file(name='filename.txt', path='a/b/c', content=b'hello world')
    create(id=workspace.id, file_content=content, user=user)

    # Verify that the base metadata entry is correct
    base_family = workspace.families.filter_by(name='base').first()
    base_metadata = Metadata.query.filter_by(id_file=file_id, family=base_family).first().json
    bucket_url = app.config["QUETZAL_GCP_DATA_BUCKET"]
    expected_metadata = {
        'id': str(file_id),
        'filename': 'filename.txt',
        'path': 'a/b/c',
        'size': 11,
        'checksum': '5eb63bbbe01eeed093cb22bb8f5acdc3',
        'url': f'{bucket_url}/{file_id}',
        'date': '2019-02-03 16:30:11.350719+00:00',
    }

    assert base_metadata == expected_metadata


def test_create_file_correct_api(app, db, db_session, make_workspace, file_id, make_file, user, mocker):
    """Creating a file sends a correct GCP API to create an object"""
    mocker.patch('google.auth.default',
                 return_value=(AnonymousCredentials(), 'mock-project'))
    mocker.patch('app.api.data.helpers.get_client',
                 return_value=Client(project='mock-project'))
    mocker.patch('google.cloud._http.JSONConnection.api_request',
                 return_value={})
    mocker.patch('app.api.data.file.uuid4', return_value=file_id)
    request_mock = mocker.patch('google.auth.transport.requests.AuthorizedSession.request')

    # A mock function to control external request. Here, there should be a call
    # to create an object in the google cloud bucket
    def create_object_side_effect(*args, **kwargs):
        result_type = namedtuple('request', ['status_code', 'headers', 'json'])
        return result_type(200,
                           {'location': 'https://www.googleapis.com/storage/filename?upload_id=xxx'}
                           if args[0] == 'POST' else {},
                           lambda: {})

    request_mock.side_effect = create_object_side_effect

    # Create a workspace with the base family because the file create function
    # assumes the workspace is correctly initialized: it must have a base family
    workspace = make_workspace(families={'base': 0}, owner=user)

    # Create a file with some dummy contents
    content = make_file(name='filename.txt', path='a/b/c', content=b'hello world')
    create(id=workspace.id, file_content=content, user=user)

    # Verify the correct calls to the API

    # There should have been two calls to the GCP API:
    # one to create the object in the bucket
    # one to send the contet
    assert request_mock.call_count == 2

    # call_args_list is a list of unittest.mock.Call objects, which can be
    # either 2- or 3-tuple. We want the 2-tuple case
    # See docs on: https://docs.python.org/3/library/unittest.mock.html#unittest.mock.call
    args1, kwargs1 = request_mock.call_args_list[0]
    args2, kwargs2 = request_mock.call_args_list[1]
    bucket = urllib.parse.urlparse(app.config["QUETZAL_GCP_DATA_BUCKET"]).netloc

    # The first call should follow
    # https://cloud.google.com/storage/docs/json_api/v1/objects/insert
    assert args1[0] == 'POST'
    assert args1[1] == f'https://www.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=resumable'
    assert json.loads(kwargs1['data']) == {'name': str(file_id)}

    # The second call should follow
    # https://cloud.google.com/storage/docs/json_api/v1/objects/update
    assert args2[0] == 'PUT'
    assert args2[1] == 'https://www.googleapis.com/storage/filename?upload_id=xxx'
    assert kwargs2['data'] == b'hello world'
    assert kwargs2['headers']['content-type'] == 'application/octet-stream'


def test_create_file_missing_workspace(missing_workspace_id, make_file, user):
    """Create a file on a missing workspace fails"""
    with pytest.raises(ObjectNotFoundException):
        create(id=missing_workspace_id, file_content=make_file(), user=user)


@pytest.mark.parametrize('state',
                         [ws for ws in WorkspaceState
                          if ws not in [WorkspaceState.READY, WorkspaceState.CONFLICT]])
def test_create_file_invalid_state(db, db_session, make_workspace, state, make_file, user):
    """Cannot create a file unless the workspace is ready"""
    # Create a workspace with the base family because the file create function
    # assumes the workspace is correctly initialized: it must have a base family
    workspace = make_workspace(families={'base': 0}, state=state)

    # Create a file with some dummy contents
    with pytest.raises(APIException):
        create(id=workspace.id, file_content=make_file(), user=user)


def test_download_file_content_in_workspace(app, db_session, make_workspace, upload_file, mocker):
    """Retrieve file contents of a file uploaded to a workspace"""
    # Create a workspace with the base family because the file create function
    # assumes the workspace is correctly initialized: it must have a base family
    workspace = make_workspace(families={'base': 0})
    known_content = b'some content bytes'
    mocker.patch('app.api.data.file._download_file', return_value=io.BytesIO(known_content))
    file_id = upload_file(workspace=workspace, content=known_content)

    headers = {'accept': 'application/octet-stream'}
    with app.test_request_context(headers=headers):
        content, code = details_w(id=workspace.id, uuid=file_id)

    assert code == 200
    assert content.data == known_content


def test_download_file_metadata_in_workspace(app, db_session, make_workspace, upload_file):
    """Retrieve file metadata of a file uploaded to a workspace"""
    # Create a workspace with the base family because the file create function
    # assumes the workspace is correctly initialized: it must have a base family
    workspace = make_workspace(families={'base': 0})
    file_id = upload_file(workspace=workspace)

    headers = {'accept': 'application/json'}
    with app.test_request_context(headers=headers):
        details, code = details_w(id=workspace.id, uuid=file_id)

    assert code == 200
    assert details['id'] == file_id
    assert 'metadata' in details


def test_download_file_content_in_global(app, db_session, committed_file, mocker):
    """Retrieve file contents of a file uploaded and committed"""
    file_id = committed_file['id']
    file_contents = committed_file['content']
    mocker.patch('app.api.data.file._download_file', return_value=io.BytesIO(file_contents))

    headers = {'accept': 'application/octet-stream'}
    with app.test_request_context(headers=headers):
        content, code = details(uuid=file_id)

    assert code == 200
    assert content.data == file_contents


def test_download_file_metadata_in_global(app, db_session, committed_file):
    """Retrieve file contents of a file uploaded and committed"""
    file_id = committed_file['id']
    file_metadata = committed_file['metadata']

    headers = {'accept': 'application/json'}
    with app.test_request_context(headers=headers):
        metadata, code = details(uuid=file_id)

    assert code == 200
    assert metadata['metadata'] == file_metadata


def test_download_file_content_correct_api(app, db_session, make_workspace, upload_file, mocker):
    """Retrieve file contents of a file uploaded to a workspace"""
    # There are a lot of mocks to do in order to test file downloading.
    result_type = namedtuple('request', ['status_code', 'headers', 'json'])
    mocker.patch('google.auth.default',
                 return_value=(AnonymousCredentials(), 'mock-project'))
    mocker.patch('app.api.data.helpers.get_client',
                 return_value=Client(project='mock-project'))
    request_mock = mocker.patch('google.cloud._http.JSONConnection.api_request',
                                side_effect=result_type(200, {'location': 'something'}, lambda: {}))
    transport_request_mock = mocker.patch('google.auth.transport.requests.AuthorizedSession.request',
                                          return_value=result_type(200, {}, lambda: {}))
    mocker.patch('google.resumable_media.requests.download.Download._write_to_stream')

    # Create workspace and with a file
    workspace = make_workspace(families={'base': 0})
    file_id = upload_file(workspace=workspace, url='gs://bucket_name/object_name')

    headers = {'accept': 'application/octet-stream'}
    with app.test_request_context(headers=headers):
        details_w(id=workspace.id, uuid=file_id)

    # the first two calls concern getting the bucket name
    assert request_mock.call_count == 2

    args1, kwargs1 = request_mock.call_args_list[0]
    args2, kwargs2 = request_mock.call_args_list[1]
    assert kwargs1['method'] == kwargs2['method'] == 'GET'
    assert kwargs1['path'] == '/b/bucket_name'
    assert kwargs2['path'] == '/b/bucket_name/o/object_name'

    # the last call concerns the downloading and should respect
    # https://cloud.google.com/storage/docs/json_api/v1/objects/get
    transport_request_mock.assert_called_once()
    args3, kwargs3 = transport_request_mock.call_args
    assert args3[0] == 'GET'
    assert args3[1] == 'https://www.googleapis.com/download/storage/v1/b/bucket_name/o/object_name?alt=media'
