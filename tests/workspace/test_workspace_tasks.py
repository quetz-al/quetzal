import urllib.parse

import pytest
from celery.exceptions import Retry
from google.cloud.storage import Client
from sqlalchemy import func

from quetzal.app.models import Family, Workspace, WorkspaceState
from quetzal.app.api.data.workspace import create
from quetzal.app.api.data.tasks import (
    wait_for_workspace, init_workspace, init_data_bucket, delete_workspace
)
from quetzal.app.api.exceptions import WorkerException


def test_create_workspace_backend_tasks(app, user, db_session, mocker):
    """Workspace create triggers three tasks in the correct order and args"""
    request = {
        'name': 'unit-test-failed-queue',
        'description': 'Unit test workspace description',
        'families': {
            'base': None,
        }
    }

    run_mock = mocker.patch('app.helpers.celery._mockable_call')
    result, code = create(body=request, user=user)

    # There should have been three calls to a celery task:
    # wait_for_workspace, init_workspace and init_data_bucket
    assert run_mock.call_count == 3

    # Each call should have the same id as argument
    # Moreover, call_args_list is a list of unittest.mock.Call objects, which
    # can be either 2- or 3-tuple. We want the 2-tuple case
    # See docs on: https://docs.python.org/3/library/unittest.mock.html#unittest.mock.call
    args1, kwargs1 = run_mock.call_args_list[0]
    args2, kwargs2 = run_mock.call_args_list[1]
    args3, kwargs3 = run_mock.call_args_list[2]

    # The signature to verify here comes from the celery_helper.mockable_call
    # function. Let's verify it was called in the correct order and with the
    # same workspace id
    #
    # kwargs should be empty
    assert {} == kwargs1 == kwargs2 == kwargs3
    # correct order
    assert args1[1].name == wait_for_workspace.name
    assert args2[1].name == init_workspace.name
    assert args3[1].name == init_data_bucket.name
    # same workspace id
    assert args1[2] == args2[2] == args3[2] == result['id']


def test_wait_for_workspace_success(workspace, db_session):
    """Wait for workspace success conditions"""
    wait_for_workspace(workspace.id)


def test_wait_for_workspace_retry(workspace, db_session):
    """Wait for workspace retries when workspace does not exist"""
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(Retry):
        wait_for_workspace(max_id + 1)


def test_init_workspace_success(db_session, make_workspace):
    """Init workspace success conditions"""
    w = make_workspace(state=WorkspaceState.INITIALIZING)
    init_workspace(w.id)
    assert True


def test_init_workspace_missing(db_session):
    """Init workspace fails when the workspace does not exist"""
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(WorkerException):
        init_workspace(max_id + 1)


@pytest.mark.parametrize('state', [ws for ws in WorkspaceState if ws != WorkspaceState.INITIALIZING])
def test_init_workspace_invalid_state(db_session, make_workspace, state):
    """Init workspace fails when the workspace is not on the correct state"""
    w = make_workspace(state=state)
    with pytest.raises(WorkerException):
        init_workspace(w.id)


def test_init_workspace_new_family(db_session, make_workspace):
    """Init workspace creates a new family when it does not exist"""
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'new': 0})
    init_workspace(w.id)
    assert w.families.count() == 1

    new_family = w.families.first()
    assert new_family.name == 'new'
    assert new_family.version == 0


def test_init_workspace_fail_missing_family(db_session, make_workspace):
    """Init workspace fails when family does not exist and its version is not zero"""
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'new': 1000})
    with pytest.raises(WorkerException):
        init_workspace(w.id)


def test_init_workspace_existing_family(db, db_session, make_workspace):
    """Init workspace finds a family when it existed before"""
    db.session.add(Family(name='existing', version=1, workspace=None))
    db.session.commit()
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'existing': 1})
    init_workspace(w.id)


def test_init_workspace_existing_family_bad_version(db, db_session, make_workspace):
    """Init workspace fails when family exist but verison is incorrect"""
    db.session.add(Family(name='existing', version=1, workspace=None))
    db.session.commit()
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'existing': 100})
    with pytest.raises(WorkerException):
        init_workspace(w.id)


def test_init_workspace_latest_version_existing(db, db_session, make_workspace, make_family):
    """Init workspace sets version to latest existing family"""
    previous_family = make_family(name='hello', version=100)
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={previous_family.name: None})
    init_workspace(w.id)

    assert w.families.count() == 1
    assert w.families.first().name == 'hello'
    assert w.families.first().version == 100
    assert w.families.first().workspace == w


def test_init_workspace_latest_version_missing(db, db_session, make_workspace, make_family):
    """Init workspace creates and sets the version to zero of a family that did not exist"""
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'new': None})
    init_workspace(w.id)

    assert w.families.count() == 1
    assert w.families.first().name == 'new'
    assert w.families.first().version == 0
    assert w.families.first().workspace == w


def test_init_data_bucket_success(db, db_session, make_workspace, mocker):
    """Init bucket send success condition"""
    # See test_init_data_bucket_correct_api for comments on these mocks
    mocker.patch('google.auth.default',
                 return_value=(None, 'mock-project'))
    mocker.patch('quetzal.app.api.data.tasks.get_client',
                 return_value=Client(project='mock-project'))
    mocker.patch('google.cloud._http.JSONConnection.api_request')

    w = make_workspace(state=WorkspaceState.INITIALIZING)
    init_data_bucket(w.id)

    # Verify the workspace state and data_url have been updated
    assert w.state == WorkspaceState.READY
    assert w.data_url is not None


def test_init_data_bucket_correct_api(db, db_session, make_workspace, mocker):
    """Init data bucket sends a correct API request"""
    # We need several mocks to verify that the bucket is created without
    # actually calling the API.
    # - the google authentication function that is called by any new client
    #   object, even if it is a fake one (this needs to be patched first
    #   because it is used on the second mock)
    # - the get_client function that produces a google client
    # - the api_request call that will do the final http request
    google_auth_mock = mocker.patch('google.auth.default',
                                    return_value=(None, 'mock-project'))
    # Note that here, mocking 'quetzal.app.api.data.helpers.get_client' will not work
    # because it is imported in 'quetzal.app.api.data.tasks'.
    # See https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    get_client_mock = mocker.patch('quetzal.app.api.data.tasks.get_client',
                                   return_value=Client(project='mock-project'))
    request_mock = mocker.patch('google.cloud._http.JSONConnection.api_request')

    w = make_workspace(state=WorkspaceState.INITIALIZING)
    init_data_bucket(w.id)

    # Verify mocks were called
    get_client_mock.assert_called()
    google_auth_mock.assert_called()
    request_mock.assert_called_once()

    # Verify that the request complies to the storage json API
    # https://cloud.google.com/storage/docs/json_api/v1/buckets/insert
    request_kwargs = request_mock.call_args[1]
    assert request_kwargs['method'] == 'POST'
    assert request_kwargs['path'] == '/b'
    assert request_kwargs['query_params'] == {'project': 'mock-project'}
    assert request_kwargs['data'] == {
        'name': urllib.parse.urlparse(w.data_url).netloc,
        'storageClass': 'REGIONAL',
        'location': 'europe-west1',
    }


def test_init_data_bucket_missing(db_session):
    """Init data bucket fails when the workspace does not exist"""
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(WorkerException):
        init_data_bucket(max_id + 1)


@pytest.mark.parametrize('state', [ws for ws in WorkspaceState if ws != WorkspaceState.INITIALIZING])
def test_init_data_bucket_invalid_state(db_session, make_workspace, state):
    """Init data bucket fails when the workspace is not on the correct state"""
    w = make_workspace(state=state)
    with pytest.raises(WorkerException):
        init_data_bucket(w.id)


def test_delete_workspace_task_success(db_session, make_workspace, mocker):
    # See test_init_data_bucket_correct_api for comments on these mocks
    mocker.patch('google.auth.default',
                 return_value=(None, 'mock-project'))
    mocker.patch('quetzal.app.api.data.tasks.get_client',
                 return_value=Client(project='mock-project'))
    request_mock = mocker.patch('google.cloud._http.JSONConnection.api_request')
    request_mock.return_value = {}

    w = make_workspace(state=WorkspaceState.DELETING, data_url='gs://bucket-name')
    delete_workspace(w.id)

    # Verify the workspace state has been updated
    assert w.state == WorkspaceState.DELETED


def test_delete_workspace_task_correct_api(db_session, make_workspace, mocker):
    """Delete workspace sends a correct API request to delete its bucket"""
    # See test_init_data_bucket_correct_api for comments on these mocks
    mocker.patch('google.auth.default',
                 return_value=(None, 'mock-project'))
    mocker.patch('quetzal.app.api.data.tasks.get_client',
                 return_value=Client(project='mock-project'))
    request_mock = mocker.patch('google.cloud._http.JSONConnection.api_request')
    request_mock.side_effect = [
        {},  # First call is when the Bucket information is retrieved
        {},  # Second call is to list all bucket objects
        {},  # Third call is to delete the bucket
    ]

    w = make_workspace(state=WorkspaceState.DELETING, data_url='gs://bucket-name')
    delete_workspace(w.id)

    # Verify that the request complies to the storage json API
    # https://cloud.google.com/storage/docs/json_api/v1/buckets/delete
    request_kwargs = request_mock.call_args[-1]
    assert request_kwargs['method'] == 'DELETE'
    assert request_kwargs['path'] == '/b/bucket-name'
    assert request_kwargs['query_params'] == {}
    assert 'data' not in request_kwargs


def test_delete_workspace_task_missing(db_session):
    """Delete workspace fails when the workspace does not exist"""
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(WorkerException):
        delete_workspace(max_id + 1)


@pytest.mark.parametrize('state', [ws for ws in WorkspaceState if ws != WorkspaceState.DELETING])
def test_delete_workspace_task_invalid_state(db_session, make_workspace, state):
    """Init data bucket fails when the workspace is not on the correct state"""
    w = make_workspace(state=state)
    with pytest.raises(WorkerException):
        delete_workspace(w.id)


# TODO: add test that uses mockable_call to verify that tasks are called by celery
# This is only done for the create_workspace case but not for the others
