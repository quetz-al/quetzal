import pytest

from app.api.data.file import update_metadata
from app.api.exceptions import APIException, ObjectNotFoundException
from app.models import WorkspaceState


def test_update_metadata_success(db_session, make_workspace, upload_file):
    """Update metadata success conditions"""
    workspace = make_workspace(families={'base': 0, 'other': 0})
    file_id = upload_file(workspace=workspace)

    new_metadata = {
        'other': {
            'key': 'value',
        }
    }
    update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)


@pytest.mark.parametrize('state',
                         [ws for ws in WorkspaceState
                          if ws not in [WorkspaceState.READY, WorkspaceState.CONFLICT]])
def test_update_metadata_invalid_state(db_session, make_workspace, upload_file, state):
    """Cannot change metadata when the workspace is not ready or in conflict"""
    # Create a workspace on READY state because we can only add files to it
    # when it is READY
    workspace = make_workspace(families={'base': 0, 'other': 0},
                               state=WorkspaceState.READY)
    file_id = upload_file(workspace=workspace)

    # Change the internal state without verification
    workspace._state = state
    db_session.add(workspace)
    db_session.commit()

    new_metadata = {
        'other': {
            'key': 'value',
        }
    }

    with pytest.raises(APIException):
        update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)


def test_update_metadata_missing_workspace(missing_workspace_id):
    """Updating the metadata on a missing workspace should fail"""
    with pytest.raises(ObjectNotFoundException):
        update_metadata(id=missing_workspace_id,
                        uuid='00000000-0000-4000-8000-000000000000',
                        body={'family': {'key': 'value'}})


@pytest.mark.parametrize('key', ['id', 'size', 'checksum', 'url'])
def test_update_metadata_id_blacklist(db_session, make_workspace, upload_file, key):
    """It should not be possible to change some keys in the base family"""
    workspace = make_workspace(families={'base': 0})
    file_id = upload_file(workspace=workspace)

    new_metadata = {
        'base': {
            key: 'some_value',
        }
    }
    with pytest.raises(APIException):
        update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)


@pytest.mark.parametrize('key', ['filename', 'path'])
def test_update_metadata_base_whitelist(db_session, make_workspace, upload_file, key):
    """It should be possible to change some specific keys in the base family"""
    workspace = make_workspace(families={'base': 0})
    file_id = upload_file(workspace=workspace)

    new_metadata = {
        'base': {
            key: 'some_value',
        }
    }

    update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)


def test_update_metadata_family_does_not_exist(db_session, make_workspace, upload_file):
    """Updating metadata of a family not present in a workspace should fail"""
    workspace = make_workspace(families={'base': 0, 'existing': 0})
    file_id = upload_file(workspace=workspace)

    new_metadata = {
        'unknown': {
            'key': 'value',
        }
    }
    with pytest.raises(APIException):
        update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)


def test_update_metadata_other_workspace():
    """Cannot update metadata of a file in another workspace"""
    raise NotImplementedError


def test_update_metadata_family_exists_global():
    """Modification of metadata on a file outside the workspace"""
    raise NotImplementedError


def test_update_metadata_family_exists_local(db_session, make_workspace, upload_file):
    """Modification of metadata on a file in a workspace"""
    workspace = make_workspace(families={'base': 0, 'existing': 0})
    file_id = upload_file(workspace=workspace)

    new_metadata = {
        'existing': {
            'new_key': 'new_value',
        }
    }

    update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)


def test_update_metadata_correct_content_global():
    """Verify exact modifications of metadata of a committed file"""
    raise NotImplementedError


def test_update_metadata_correct_content_local(db_session, make_workspace, upload_file):
    """Verify exact modifications of metadata of a file in a workspace"""
    workspace = make_workspace(families={'base': 0, 'existing': 0})
    file_id = upload_file(workspace=workspace, name='filename.txt',
                          path='a/b/c', content=b'hello world',
                          url='gs://some_bucket/some_name')

    new_metadata = {
        'existing': {
            'string': 'hello',
            'integer': 123,
            'float': 0.5,
            'null': None,
            'list': ['a', 'b', 'c'],
            'object': {'a': 'A', 'b': 'B', 'c': 'C'},
        }
    }

    result, _ = update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)
    expected_result = new_metadata.copy()
    expected_result['existing']['id'] = file_id
    expected_result['base'] = {
        'id': file_id,
        'filename': 'filename.txt',
        'path': 'a/b/c',
        'checksum': '5eb63bbbe01eeed093cb22bb8f5acdc3',
        'size': 11,
        'url': 'gs://some_bucket/some_name',
    }

    assert result == expected_result
