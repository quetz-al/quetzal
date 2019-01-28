import pytest
import warnings

from app.api.data.file import update_metadata
from app.api.exceptions import APIException, ObjectNotFoundException
from app.models import Family, Metadata, WorkspaceState


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


@pytest.mark.parametrize('key', ['id', 'size', 'checksum', 'url', 'date'])
def test_update_metadata_base_blacklist(db_session, make_workspace, upload_file, key):
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


def test_update_metadata_id_blacklist(db_session, make_workspace, upload_file):
    """The "id" metadata cannot be modified on other families"""
    workspace = make_workspace(families={'base': 0, 'other': 0})
    file_id = upload_file(workspace=workspace)

    new_metadata = {
        'other': {
            'id': '00000000-0000-4000-8000-000000000000',
        }
    }
    with pytest.raises(APIException):
        update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)


def test_update_metadata_other_workspace():
    """Cannot update metadata of a file in another workspace"""
    warnings.warn('Unit test not implemented', UserWarning)


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


def test_update_metadata_family_exists_global():
    """Modification of metadata on a file outside the workspace"""
    # Needs implementation of commit
    warnings.warn('Unit test not implemented', UserWarning)


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
    # Needs implementation of commit
    warnings.warn('Unit test not implemented', UserWarning)


def test_update_metadata_correct_content_local(db_session, make_workspace, upload_file):
    """Verify exact modifications of metadata of a file in a workspace"""
    workspace = make_workspace(families={'base': 0, 'existing': 0})
    file_id = upload_file(workspace=workspace, name='filename.txt',
                          path='a/b/c', content=b'hello world',
                          url='gs://some_bucket/some_name',
                          date='2019-02-03 16:30:11.350719+00:00')

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
        'date': '2019-02-03 16:30:11.350719+00:00',
    }

    assert result == expected_result


def test_update_metadata_correct_db_content_local(db_session, make_workspace, upload_file):
    """Verify exact database modifications of metadata of a file in a workspace"""
    workspace = make_workspace(families={'base': 0, 'other': 0})
    file_id = upload_file(workspace=workspace, name='filename.txt',
                          path='a/b/c', content=b'hello world',
                          url='gs://some_bucket/some_name',
                          date='2019-02-03 16:30:11.350719+00:00')

    new_metadata = {
        'other': {
            'string': 'hello',
            'integer': 123,
            'float': 0.5,
            'null': None,
            'list': ['a', 'b', 'c'],
            'object': {'a': 'A', 'b': 'B', 'c': 'C'},
        }
    }

    update_metadata(id=workspace.id, uuid=file_id, body=new_metadata)

    file_metadata_qs = Metadata.query.filter_by(id_file=file_id)
    assert file_metadata_qs.count() == 2

    base_family = workspace.families.filter_by(name='base').first()
    other_family = workspace.families.filter_by(name='other').first()
    base_metadata_db = file_metadata_qs.filter_by(family=base_family).first()
    other_metadata_db = file_metadata_qs.filter_by(family=other_family).first()
    assert base_metadata_db is not None
    assert other_metadata_db is not None

    base_metadata_expected = {
        'id': file_id,
        'filename': 'filename.txt',
        'path': 'a/b/c',
        'checksum': '5eb63bbbe01eeed093cb22bb8f5acdc3',
        'size': 11,
        'url': 'gs://some_bucket/some_name',
        'date': '2019-02-03 16:30:11.350719+00:00',
    }
    other_metadata_expected = new_metadata['other'].copy()
    other_metadata_expected['id'] = file_id
    assert base_metadata_db.json == base_metadata_expected
    assert other_metadata_db.json == other_metadata_expected


def test_update_metadata_db_records(make_workspace, upload_file):
    """Changing existing metadata reuses the previous entry on the DB"""
    workspace = make_workspace(families={'base': 0, 'other': 0})
    file_id = upload_file(workspace=workspace)

    master_query = (
        Metadata
        .query
        .filter_by(id_file=file_id)
        .join(Family)
    )
    base_query = master_query.filter(Family.name == 'base')
    other_query = master_query.filter(Family.name == 'other')
    prev_meta_base_ids = {m.id for m in base_query.all()}
    prev_meta_other_ids = {m.id for m in other_query.all()}

    # Modify the base metadata
    new_metadata_1 = {
        'base': {
            'path': 'new/path/value',
        }
    }
    update_metadata(id=workspace.id, uuid=file_id, body=new_metadata_1)

    # Verify there are still the same number of objects
    new_meta_base_ids = {m.id for m in base_query.all()}
    assert new_meta_base_ids == prev_meta_base_ids

    # Now modify the other metadata
    new_metadata_2 = {
        'other': {
            'key': 'value',
        }
    }
    update_metadata(id=workspace.id, uuid=file_id, body=new_metadata_2)

    # Verify there is only one new object
    new_meta_other_ids_1 = {m.id for m in other_query.all()}
    assert len(new_meta_other_ids_1 - prev_meta_other_ids) == 1

    # Modify the other metadata again
    new_metadata_3 = {
        'other': {
            'another_key': 'another value',
        }
    }
    update_metadata(id=workspace.id, uuid=file_id, body=new_metadata_3)

    # Verify there are still the same number of objects
    new_meta_other_ids_2 = {m.id for m in other_query.all()}
    assert new_meta_other_ids_1 == new_meta_other_ids_2


def test_set_metadata_success():
    warnings.warn('Unit test not implemented', UserWarning)


@pytest.mark.parametrize('state',
                         [ws for ws in WorkspaceState
                          if ws not in [WorkspaceState.READY, WorkspaceState.CONFLICT]])
def test_set_metadata_invalid_state(state):
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_missing_worspace():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_base_blacklist():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_base_whitelist():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_id_blacklist():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_other_workspace():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_family_does_not_exist():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_famliy_exist_local():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_correct_content_global():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_correct_content_local():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_correct_db_contents():
    warnings.warn('Unit test not implemented', UserWarning)


def test_set_metadata_db_records():
    warnings.warn('Unit test not implemented', UserWarning)
