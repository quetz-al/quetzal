"""Unit tests for creating a workspace through the route method"""

import pytest

from celery.exceptions import OperationalError

from app.api.exceptions import APIException
from app.api.data.workspace import create
from app.models import Workspace


def test_create_success(user, mocker):
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

    # Name, descrption and families should be kept as requested
    assert response['name'] == request['name']
    assert response['description'] == request['description']
    assert response['families'] == request['families']


def test_create_backend_task(user, mocker):
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


def test_create_failed_task(user, mocker):
    existing_workspaces ={w.id for w in Workspace.query.all()}

    request = {
        'name': 'unit-test-failed-task',
        'description': 'Unit test workspace description',
        'families': {
            'base': None,
            'other': 1,
        }
    }

    async_mock = mocker.patch('celery.canvas._chain.apply_async')
    async_mock.side_effect = OperationalError('Mocked operational error')

    with pytest.raises(APIException) as exc_info:
        create(body=request, user=user)

    assert exc_info.value.status == 503

    # Verify that no workspace was created
    new_workspaces = {w.id for w in Workspace.query.all()}
    assert existing_workspaces == new_workspaces


def test_create_repeated_workspace(user, make_workspace, mocker):
    """Creating a repeated workspace through the route gives an exception"""
    name = 'repeated-test'
    make_workspace(name=name)

    request = {
        'name': name,
        'description': 'some description',
        'families': {'base': None},
    }

    # Mock the celery part just in case so there is no initialization
    mocker.patch('celery.canvas._chain.apply_async')

    with pytest.raises(APIException) as exc_info:
        create(body=request, user=user)

    assert exc_info.value.status == 400


def test_base_auto(user, mocker):
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
