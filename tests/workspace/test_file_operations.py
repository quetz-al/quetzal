import logging
import uuid
from collections import namedtuple

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud.storage import Client

from app.api.data.file import create
from app.api.exceptions import APIException
from app.models import Metadata, WorkspaceState


@pytest.fixture(scope='function')
def file_id():
    return uuid.uuid4()


def test_create_file_success(db, db_session, make_workspace, file_id, mocker):
    """File create on success conditions"""
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
    content = b'content'
    create(id=workspace.id, body=content)

    # There should be a base metadata entry
    base_family = workspace.families.filter_by(name='base').first()
    base_metadata = Metadata.query.filter_by(id_file=file_id, family=base_family).first()
    assert base_metadata is not None

    # There should be only one new metadata entry
    count = Metadata.query.filter_by(id_file=file_id).count()
    assert count == 1


def test_create_file_missing_base(db, db_session, make_workspace, caplog):
    """Adding a file on a workspace without base family should fail"""
    # Explicitly make a workspace without base family. This should never happen
    # but we want to make sure anyways
    workspace = make_workspace(families={})

    # Create a file with some dummy contents
    content = b'content'
    # caplog.at_level:
    # capture the logger.error log message emitted when the queue fails
    with caplog.at_level(logging.CRITICAL, logger='app.api.data.workspace'):
        with pytest.raises(APIException):
            create(id=workspace.id, body=content)


def test_create_file_correct_metadata():
    """Creating a file creates the correct metadata"""
    pass


def test_create_file_correct_api():
    """Creating a file sends a correct GCP API to create an object"""
    pass


def test_create_file_missing_workspace():
    """Create a file on a missing workspace fails"""
    pass


@pytest.mark.parametrize('state',
                         [ws for ws in WorkspaceState
                          if ws not in [WorkspaceState.READY, WorkspaceState.CONFLICT]])
def test_create_file_invalid_state(db, db_session, make_workspace, state):
    """Cannot create a file unless the workspace is ready"""
    # Create a workspace with the base family because the file create function
    # assumes the workspace is correctly initialized: it must have a base family
    workspace = make_workspace(families={'base': 0}, state=state)

    # Create a file with some dummy contents
    content = b'content'
    with pytest.raises(APIException):
        create(id=workspace.id, body=content)
