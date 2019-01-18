import urllib.parse

import pytest
from celery.exceptions import Retry
from sqlalchemy import func

from app.models import Family, Workspace, WorkspaceState
from app.api.data.tasks import wait_for_workspace, init_workspace, init_data_bucket
from app.api.exceptions import WorkerException


def test_wait_for_workspace_success(workspace, db_session):
    wait_for_workspace(workspace.id)
    assert True


def test_wait_for_workspace_retry(workspace, db_session):

    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(Retry):
        wait_for_workspace(max_id + 1)


def test_init_workspace_success(db_session, make_workspace):
    w = make_workspace(state=WorkspaceState.INITIALIZING)
    init_workspace(w.id)
    assert True


def test_init_workspace_missing(db_session):
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(WorkerException):
        init_workspace(max_id + 1)


@pytest.mark.parametrize('state', [ws for ws in WorkspaceState if ws != WorkspaceState.INITIALIZING])
def test_init_workspace_invalid_state(db_session, make_workspace, state):
    w = make_workspace(state=state)
    with pytest.raises(WorkerException):
        init_workspace(w.id)


def test_init_workspace_new_family(db_session, make_workspace):
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'new': 0})
    init_workspace(w.id)
    assert w.families.count() == 1

    new_family = w.families.first()
    assert new_family.name == 'new'
    assert new_family.version == 0


def test_init_workspace_fail_missing_family(db_session, make_workspace):
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'new': 1000})
    with pytest.raises(WorkerException):
        init_workspace(w.id)


def test_init_workspace_existing_family(db, db_session, make_workspace):
    db.session.add(Family(name='existing', version=1, workspace=None))
    db.session.commit()
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'existing': 1})
    init_workspace(w.id)
    assert True


def test_init_workspace_existing_family_bad_version(db, db_session, make_workspace):
    db.session.add(Family(name='existing', version=1, workspace=None))
    db.session.commit()
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'existing': 100})
    with pytest.raises(WorkerException):
        init_workspace(w.id)


def test_init_workspace_latest_version_existing(db, db_session, make_workspace, make_family):
    previous_family = make_family(version=100)
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={previous_family.name: None})
    init_workspace(w.id)

    assert w.families.count() == 1
    assert w.families.first().name == previous_family.name
    assert w.families.first().version == previous_family.version
    assert w.families.first().workspace == w


def test_init_workspace_latest_version_missing(db, db_session, make_workspace, make_family):
    w = make_workspace(state=WorkspaceState.INITIALIZING,
                       families={'new': None})
    init_workspace(w.id)

    assert w.families.count() == 1
    assert w.families.first().name == 'new'
    assert w.families.first().version == 0
    assert w.families.first().workspace == w


def test_init_data_bucket_success(db, db_session, make_workspace, mocker):
    from google.cloud.storage import Client
    w = make_workspace(state=WorkspaceState.INITIALIZING)
    get_client_mock = mocker.patch('app.api.data.helpers.get_client')
    google_auth_mock = mocker.patch('google.auth.default')
    bucket_create_mock = mocker.patch('google.cloud.storage.bucket.Bucket.create')

    google_auth_mock.return_value = None, 'mock-project'
    get_client_mock.return_value = Client()

    init_data_bucket(w.id)

    bucket_create_mock.assert_called_once()
    assert w.state == WorkspaceState.READY
    assert w.data_url is not None


def test_init_data_bucket_missing(db_session):
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0

    with pytest.raises(WorkerException):
        init_data_bucket(max_id + 1)


@pytest.mark.parametrize('state', [ws for ws in WorkspaceState if ws != WorkspaceState.INITIALIZING])
def test_init_data_bucket_invalid_state(db_session, make_workspace, state):
    w = make_workspace(state=state)
    with pytest.raises(WorkerException):
        init_data_bucket(w.id)
