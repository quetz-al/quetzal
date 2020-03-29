import pytest
import requests
from flask_principal import identity_changed, Identity

from quetzal.app.api.exceptions import APIException
from quetzal.app.api.data.workspace import commit, create, delete, details, fetch, scan
from quetzal.app.security import WorkspaceNeed


@pytest.mark.usefixtures('mocked_chained_apply_async')
def test_authorized_create_workspace(app, workspace_request, make_user):
    """The public_write role authorizes to create a workspace"""
    user = make_user(roles=['public_write'])

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))
        _, code = create(body=workspace_request, user=user)

    assert code == requests.codes.created


@pytest.mark.usefixtures('mocked_chained_apply_async')
@pytest.mark.parametrize('role', [None, 'public_read', 'public_commit'])
def test_unauthorized_create_workspace(app, workspace_request, make_user, mocker, role):
    """All roles different than public_write do not authorize to create a workspace"""
    roles = role or []
    user = make_user(roles=roles)

    # Mock db.session.commit to verify no data is committed to the database
    commit_mock = mocker.patch('quetzal.app.db.session.commit')

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))

        with pytest.raises(APIException) as exc_info:
            create(body=workspace_request, user=user)

    assert exc_info.value.status == requests.codes.forbidden
    commit_mock.assert_not_called()


def test_authorized_fetch_workspace(app, make_user):
    """The public_read role authorizes to list workspaces"""
    user = make_user(roles=['public_read'])

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))
        _, code = fetch()

    assert code == requests.codes.ok


@pytest.mark.parametrize('role', [None, 'public_write', 'public_commit'])
def test_unauthorized_fetch_workspace(app, make_user, role):
    """All roles different than public_read do not authorize to list workspaces"""
    roles = role or []
    user = make_user(roles=roles)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))

        with pytest.raises(APIException) as exc_info:
            fetch()

    assert exc_info.value.status == requests.codes.forbidden


def test_authorized_details_workspace(app, user, make_workspace):
    """A user who owns a workspace can retrieve is details"""
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))
        _, code = details(wid=workspace.id)

    assert code == requests.codes.ok


def test_unauthorized_user_details_workspace(app, make_user, make_workspace):
    """A user who does not own a workspace cannot retrieve its details"""
    owner = make_user()
    other = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=owner)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(other.id, 'unit-test'))

        with pytest.raises(APIException) as exc_info:
            details(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden


def test_unauthorized_revoked_details_workspace(app, make_user, make_workspace):
    """A user with revoked permissions on a workspace cannot retrieve its details """
    user = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity = Identity(user.id, 'unit-test')
        identity_changed.send(app, identity=identity)
        # Revoke any provided WriteWorkspaceNeed
        identity.provides = set(p for p in identity.provides
                                if not isinstance(p, WorkspaceNeed) or p.operation != 'write')
        with pytest.raises(APIException) as exc_info:
            details(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_authorized_delete_workspace(app, user, make_workspace):
    """A user who owns a workspace can delete it"""
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))
        _, code = delete(wid=workspace.id)

    assert code == requests.codes.accepted


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_unauthorized_user_delete_workspace(app, make_user, make_workspace):
    """A user who does not own a workspace cannot delete it"""
    owner = make_user()
    other = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=owner)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(other.id, 'unit-test'))

        with pytest.raises(APIException) as exc_info:
            delete(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_unauthorized_revoked_delete_workspace(app, make_user, make_workspace):
    """A user with revoked permission cannot delete a workspace"""
    user = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity = Identity(user.id, 'unit-test')
        identity_changed.send(app, identity=identity)
        # Revoke any provided WriteWorkspaceNeed
        identity.provides = set(p for p in identity.provides
                                if not isinstance(p, WorkspaceNeed) or p.operation != 'write')
        with pytest.raises(APIException) as exc_info:
            delete(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_authorized_commit_workspace(app, user, make_workspace):
    """A user who owns a workspace can commit it"""
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))
        _, code = commit(wid=workspace.id)

    assert code == requests.codes.accepted


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_unauthorized_user_commit_workspace(app, make_user, make_workspace):
    """A user who does not own a workspace cannot commit it"""
    owner = make_user()
    other = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=owner)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(other.id, 'unit-test'))

        with pytest.raises(APIException) as exc_info:
            commit(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_unauthorized_revoked_commit_workspace(app, make_user, make_workspace):
    """A user with revoked permissions on a workspace cannot commit it"""
    user = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity = Identity(user.id, 'unit-test')
        identity_changed.send(app, identity=identity)
        # Revoke any provided WriteWorkspaceNeed
        identity.provides = set(p for p in identity.provides
                                if not isinstance(p, WorkspaceNeed) or p.operation != 'write')
        with pytest.raises(APIException) as exc_info:
            commit(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_authorized_scan_workspace(app, user, make_workspace):
    """A user who owns a workspace can scan it"""
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(user.id, 'unit-test'))
        _, code = scan(wid=workspace.id)

    assert code == requests.codes.accepted


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_unauthorized_user_scan_workspace(app, make_user, make_workspace):
    """A user who does not own a workspace cannot scan it"""
    owner = make_user()
    other = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=owner)

    with app.test_request_context():
        identity_changed.send(app, identity=Identity(other.id, 'unit-test'))

        with pytest.raises(APIException) as exc_info:
            scan(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden


@pytest.mark.usefixtures('mocked_signature_apply_async')
def test_unauthorized_revoked_scan_workspace(app, make_user, make_workspace):
    """A user with revoked permissions on a workspace cannot scan it"""
    user = make_user(roles=['public_read', 'public_write', 'public_commit'])
    workspace = make_workspace(user=user)

    with app.test_request_context():
        identity = Identity(user.id, 'unit-test')
        identity_changed.send(app, identity=identity)
        # Revoke any provided WriteWorkspaceNeed
        identity.provides = set(p for p in identity.provides
                                if not isinstance(p, WorkspaceNeed) or p.operation != 'write')
        with pytest.raises(APIException) as exc_info:
            scan(wid=workspace.id)

    assert exc_info.value.status == requests.codes.forbidden
