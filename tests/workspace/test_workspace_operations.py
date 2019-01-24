"""Unit tests for creating a workspace through the route method"""
import itertools
import logging

import pytest

from kombu.exceptions import OperationalError
from sqlalchemy import func

from app.api.exceptions import APIException, ObjectNotFoundException
from app.api.data.workspace import create, fetch, details, delete
from app.models import Workspace, WorkspaceState


def test_create_workspace_success(user, db_session, mocker):
    """Create workspace success conditions"""
    request = {
        'name': 'unit-test-create',
        'description': 'Unit test workspace description',
        'families': {
            'base': None,
            'other': 1,
        }
    }

    # Mock the celery part just in case so there is no initialization
    mocker.patch('celery.canvas._chain.apply_async')
    response, code = create(body=request, user=user)

    assert code == 201

    # Name, description and families should be kept as requested
    assert response['name'] == request['name']
    assert response['description'] == request['description']
    assert response['families'] == request['families']
    assert response['owner'] == user.username

    # Initial state should be INITIALIZING
    assert response['state'] == WorkspaceState.INITIALIZING.name


def test_create_workspace_calls_backend_task(user, db_session, mocker):
    """A celery task should be called in success conditions"""
    request = {
        'name': 'unit-test-task',
        'description': 'Unit test workspace description',
        'families': {
            'base': None,
            'other': 1,
        }
    }

    async_mock = mocker.patch('celery.canvas._chain.apply_async')
    create(body=request, user=user)
    async_mock.assert_called_once()


def test_create_workspace_handles_queue_fail(user, db_session, mocker, caplog):
    """When the queue is unavailable, workspace creation fails graciously"""
    request = {
        'name': 'unit-test-failed-queue',
        'description': 'Unit test workspace description',
        'families': {
            'base': None,
            'other': 1,
        }
    }

    async_mock = mocker.patch('celery.canvas._chain.apply_async')
    async_mock.side_effect = OperationalError('Mocked operational error')
    commit_mock = mocker.patch('app.db.session.commit')

    # caplog.at_level:
    # capture the logger.error log message emitted when the queue fails
    with caplog.at_level(logging.CRITICAL, logger='app.api.data.workspace'):
        with pytest.raises(APIException) as exc_info:
            create(body=request, user=user)

    assert exc_info.value.status == 503

    # Verify that no workspace was created
    commit_mock.assert_not_called()


def test_create_workspace_fails_duplicate_name(db_session, workspace, mocker):
    """Creating a repeated workspace through the route gives an exception"""
    owner = workspace.owner
    request = {
        'name': workspace.name,
        'description': 'some description',
        'families': {'base': None},
    }

    # Mock the celery part just in case so there is no initialization
    mocker.patch('celery.canvas._chain.apply_async')

    with pytest.raises(APIException) as exc_info:
        create(body=request, user=owner)

    assert exc_info.value.status == 400


def test_create_workspace_adds_base_family(user, db_session, mocker):
    """Base family is added when not present"""
    request = {
        'name': 'unit-test-base-auto',
        'description': 'Unit test workspace description',
        'families': {}
    }

    # Mock the celery part just in case so there is no initialization
    mocker.patch('celery.canvas._chain.apply_async')

    response, code = create(body=request, user=user)
    assert 'base' in response['families']


def test_fetch_workspaces_success(app, db, db_session, user):
    """Fetch returns all existing workspaces"""
    existing = sorted([w.to_dict() for w in Workspace.query.all()],
                      key=lambda w: w['id'])

    with app.test_request_context():
        result, code = fetch(user=user)

    fetched = sorted(result, key=lambda w: w['id'])

    for w1, w2 in itertools.zip_longest(existing, fetched):
        assert w1 == w2


def test_details_workspace_success(app, db_session, workspace):
    """Retrieving details succeeds for existing workspace"""
    with app.test_request_context():
        result, code = details(id=workspace.id)

    assert workspace.to_dict() == result


def test_details_workspace_missing(app, db_session):
    """Retrieving details fails for workspaces that do not exist"""

    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with app.test_request_context():
        with pytest.raises(ObjectNotFoundException) as exc_info:
            # max_id + 1 should not exist
            details(id=max_id+1)

    assert exc_info.value.status == 404


@pytest.mark.parametrize('state', [
    WorkspaceState.READY, WorkspaceState.INVALID, WorkspaceState.CONFLICT,
])
def test_delete_workspace_success(db_session, make_workspace, state, mocker):
    """Delete workspace success conditions"""
    w = make_workspace(state=state)

    mocker.patch('celery.canvas.Signature.apply_async')
    result, code = delete(id=w.id)

    assert code == 202
    assert w.to_dict() == result

    # Workspace must be in the DELETING state
    assert w.state == WorkspaceState.DELETING


def test_delete_workspace_calls_backend_task(db_session, make_workspace, mocker):
    """Delete workspace schedules a celery task"""
    w = make_workspace()

    async_mock = mocker.patch('celery.canvas.Signature.apply_async')
    delete(id=w.id)

    async_mock.assert_called_once()


def test_delete_workspace_missing(app, db_session):
    """Delete workspace fails when the workspace is missing"""
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(ObjectNotFoundException) as exc_info:
        # max_id + 1 should not exist
        delete(id=max_id+1)

    assert exc_info.value.status == 404


@pytest.mark.parametrize('state', [
    WorkspaceState.INITIALIZING, WorkspaceState.SCANNING, WorkspaceState.UPDATING,
    WorkspaceState.COMMITTING, WorkspaceState.DELETING, WorkspaceState.DELETED,
])
def test_delete_invalid_state(app, db_session, state, make_workspace, mocker):
    """Cannot delete workspace that is not on the correct state"""
    w = make_workspace(state=state)
    mocker.patch('celery.canvas.Signature.apply_async')

    with pytest.raises(APIException) as exc_info:
        delete(id=w.id)

    assert exc_info.value.status == 412
