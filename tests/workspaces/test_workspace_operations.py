import logging
import operator
from typing import Dict

import pytest
import requests
from kombu.exceptions import OperationalError

from quetzal.app.api.data.workspace import create, delete, details, fetch
from quetzal.app.api.exceptions import APIException, ObjectNotFoundException
from quetzal.app.models import User, Workspace, WorkspaceState


@pytest.fixture(scope='function')
def workspace_request(request) -> Dict:
    """A workspace request dictionary as defined in create workspace endpoint

    Only the name and description are set. No specific family is set other than
    the base family.
    """
    return {
        'name': f'unit-test-{request.function.__name__}',
        'description': f'Unit test for {request.function.__name__}',
        'temporary': False,
        'families': {
            'base': None,
        }
    }


@pytest.fixture(scope='function')
def user(make_user) -> User:
    return make_user()


@pytest.mark.usefixtures('mocked_chained_apply_async', 'mocked_permissions')
def test_create_workspace(workspace_request, user):
    """Test successful workspace creation"""
    workspace_request['families'] = {
        'another_family': 123,
        # While the version of "another_family" may be impossible to achieve,
        # the workspace create operation does not handle it and should keep
        # the request as-is. It will be the worker who handles this.
    }
    # Note this part needs a mocked celery apply_async and flask_principal permissions
    response, code = create(body=workspace_request, user=user)
    assert code == requests.codes.created

    # Name, description and families should be kept as requested
    assert response['name'] == workspace_request['name']
    assert response['description'] == workspace_request['description']
    assert response['families'] == workspace_request['families']
    assert response['owner'] == user.username

    # Initial state must be INITIALIZING
    assert response['status'] == WorkspaceState.INITIALIZING.name


@pytest.mark.usefixtures('mocked_permissions')
def test_create_workspace_calls_backend_task(workspace_request, user, mocked_chained_apply_async):
    """Test that creating a new workspace schedules a celery task"""
    # Note this part needs a mocked celery apply_sync and flask_principal permissions
    create(body=workspace_request, user=user)
    mocked_chained_apply_async.assert_called_once()


@pytest.mark.usefixtures('mocked_permissions')
def test_create_workspace_handles_queue_fail(workspace_request, user, mocked_chained_apply_async, mocker, caplog):
    """When the queue is unavailable, workspace creation fails graciously"""
    mocked_chained_apply_async.side_effect = OperationalError('Mocked operational error')

    # Mock db.session.commit to verify no data is committed to the database
    commit_mock = mocker.patch('quetzal.app.db.session.commit')

    # caplog.at_level:
    # capture the logger.error log message emitted when the queue fails
    with caplog.at_level(logging.CRITICAL, logger='quetzal.app.api.data.workspace'):
        with pytest.raises(APIException) as exc_info:
            create(body=workspace_request, user=user)

    assert exc_info.value.status == requests.codes.service_unavailable
    commit_mock.assert_not_called()


@pytest.mark.usefixtures('mocked_permissions', 'mocked_chained_apply_async')
def test_create_workspace_adds_base_family(workspace_request, user):
    """Base family is added when not present"""
    workspace_request['families'].pop('base')

    response, code = create(body=workspace_request, user=user)
    assert code == requests.codes.created
    assert 'base' in response['families']


@pytest.mark.usefixtures('mocked_permissions', 'mocked_chained_apply_async')
def test_duplicate_name_owner(workspace, workspace_request, user, caplog):
    """Creating a workspace with the same name and owner gives an exception"""

    workspace_request['name'] = workspace.name
    owner = workspace.owner
    with caplog.at_level(logging.CRITICAL, logger='quetzal.app.api.data.workspace'):
        with pytest.raises(APIException) as exc_info:
            create(body=workspace_request, user=owner)

    assert exc_info.value.status == requests.codes.bad_request


@pytest.mark.usefixtures('mocked_permissions')
def test_fetch_workspaces_success(app, make_workspace):
    """Fetch returns all existing workspaces"""
    for _ in range(10):
        make_workspace()
    with app.test_request_context(query_string='per_page=100000&deleted=true'):
        paginated_results, code = fetch(user=user)

    get_id_attr = operator.attrgetter('id')
    get_id_key = operator.itemgetter('id')
    known_ids = set(get_id_attr(w) for w in Workspace.query.all())
    result_ids = set(get_id_key(r) for r in paginated_results['results'])
    assert known_ids == result_ids


@pytest.mark.usefixtures('mocked_permissions')
def test_details_workspace(app, workspace):
    """Retrieving details succeeds for existing workspace"""

    with app.test_request_context():
        result, code = details(wid=workspace.id)

    assert workspace.to_dict() == result


@pytest.mark.usefixtures('mocked_permissions')
def test_details_workspace_missing(app, missing_workspace_id):
    """Retrieving details fails for workspaces that do not exist"""
    with app.test_request_context():
        with pytest.raises(ObjectNotFoundException) as exc_info:
            # max_id + 1 should not exist
            details(wid=missing_workspace_id)

    assert exc_info.value.status == requests.codes.not_found


@pytest.mark.usefixtures('mocked_permissions', 'mocked_signature_apply_async')
@pytest.mark.parametrize('state', [
    WorkspaceState.READY, WorkspaceState.INVALID, WorkspaceState.CONFLICT,
])
def test_delete_workspace(db_session, make_workspace, state):
    """Delete workspace success conditions"""
    workspace = make_workspace(state=state)

    result, code = delete(user=workspace.owner, wid=workspace.id)

    assert code == requests.codes.accepted
    assert workspace.to_dict() == result

    # Workspace must be in the DELETING state
    assert workspace.state == WorkspaceState.DELETING


@pytest.mark.usefixtures('mocked_permissions')
def test_delete_workspace_calls_backend_task(workspace, mocked_signature_apply_async):
    """Delete workspace schedules a celery task"""
    delete(user=workspace.owner, wid=workspace.id)
    mocked_signature_apply_async.assert_called_once()


def test_delete_workspace_missing(user, missing_workspace_id):
    """Delete workspace fails when the workspace is missing"""
    # Get the latest workspace id in order to request one that does not exist
    with pytest.raises(ObjectNotFoundException) as exc_info:
        # max_id + 1 should not exist
        delete(user=user, wid=missing_workspace_id)

    assert exc_info.value.status == requests.codes.not_found


@pytest.mark.usefixtures('mocked_permissions', 'mocked_signature_apply_async')
@pytest.mark.parametrize('state', [
    WorkspaceState.INITIALIZING, WorkspaceState.SCANNING, WorkspaceState.UPDATING,
    WorkspaceState.COMMITTING, WorkspaceState.DELETING, WorkspaceState.DELETED,
])
def test_delete_invalid_state(make_workspace, state):
    """Cannot delete workspace that is not on the correct state"""
    workspace = make_workspace(state=state)
    with pytest.raises(APIException) as exc_info:
        delete(user=user, wid=workspace.id)

    assert exc_info.value.status == requests.codes.precondition_failed


@pytest.mark.skip(reason='Not implemented')
def test_commit_workspace():
    """Commit workspace success conditions"""
    pass


@pytest.mark.skip(reason='Not implemented')
def test_scan_workspace():
    """Scan workspace success conditions"""
    pass
