"""Unit tests for creating a workspace through the route method"""
import itertools

import pytest

from celery.exceptions import OperationalError

from app.api.exceptions import APIException
from app.api.data.workspace import create, fetch, details
from app.models import Workspace


def test_create_workspace_success(tester_user, db_session, mocker):
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
    response, code = create(body=request, user=tester_user)

    assert code == 201

    # Name, description and families should be kept as requested
    assert response['name'] == request['name']
    assert response['description'] == request['description']
    assert response['families'] == request['families']
    assert response['owner'] == tester_user.username


def test_create_workspace_calls_backend_task(tester_user, db_session, mocker):
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
    create(body=request, user=tester_user)
    async_mock.assert_called_once()


def test_create_workspace_handles_queue_fail(tester_user, db_session, mocker):
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

    with pytest.raises(APIException) as exc_info:
        create(body=request, user=tester_user)

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


def test_create_workspace_adds_base_family(tester_user, db_session, mocker):
    """Base family is added when not present"""
    request = {
        'name': 'unit-test-base-auto',
        'description': 'Unit test workspace description',
        'families': {}
    }

    # Mock the celery part just in case so there is no initialization
    mocker.patch('celery.canvas._chain.apply_async')

    response, code = create(body=request, user=tester_user)
    assert 'base' in response['families']


def test_fetch_workspaces_success(app, db, db_session, tester_user, make_workspace):
    """Fetch returns all existing workspaces"""
    existing = sorted([w.to_dict() for w in Workspace.query.all()],
                      key=lambda w: w['id'])

    with app.test_request_context():
        result, code = fetch(user=tester_user)

    fetched = sorted(result, key=lambda w: w['id'])

    for w1, w2 in itertools.zip_longest(existing, fetched):
        assert w1 == w2


def test_details_workspace_success(app, db_session, make_workspace):
    """Retrieving details succeeds for existing workspace"""
    w = make_workspace()

    with app.test_request_context():
        result, code = details(id=w.id)

    assert w.to_dict() == result


def test_details_workspace_missing(app, db_session, make_workspace):
    """Retriving details fails for workspaces that do not exist"""

    with app.test_request_context():
        with pytest.raises(APIException) as exc_info:
            details(id=-1)

    assert exc_info.value.status == 404

