"""Common fixtures for the data api tests"""
import datetime
import io
import os
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import func

from app.models import Family, Metadata, Workspace, WorkspaceState


@pytest.fixture(scope='function')
def make_workspace(db, db_session, user, request):
    """Factory method to create workspaces for unit tests"""

    counter = 1

    def _make_workspace(name=None, state=None, owner=None, families=None, data_url=None):
        nonlocal counter
        # Create workspace on the database
        if name is None:
            name = f'w-{request.function.__name__}-{counter}'
            description = f'Fixture workspace #{counter} created by factory'
            counter += 1
        else:
            description = 'Fixture workspace created by factory'

        workspace = Workspace(name=name, description=description, owner=owner or user, data_url=data_url)
        # Change the underlying state without respecting the transitions
        workspace._state = state or WorkspaceState.READY
        db.session.add(workspace)

        # Add families if any
        families = families or {}
        for name, version in families.items():
            family = Family(name=name, version=version, workspace=workspace)
            db.session.add(family)

        # Note that this commit will also include the user because it is a
        # related model.
        db.session.commit()

        return workspace

    return _make_workspace


@pytest.fixture(scope='function')
def workspace(make_workspace):
    """Workspace with the default parameters of the workspace factory"""
    workspace = make_workspace()
    return workspace


@pytest.fixture(scope='function')
def missing_workspace_id(db, db_session):
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0
    return max_id + 1


@pytest.fixture(scope="function")
def make_family(db, db_session, user, request):
    """Family factory method"""

    counter = 1

    def _make_family(name=None, version=0, workspace=None):
        nonlocal counter
        if name is None:
            name = f'fam-{request.function.__name__}-{counter}'
            description = f'Fixture family #{counter} created by factory'
            counter += 1
        else:
            description = 'Fixture family created by factory'

        family = Family(name=name, version=version, description=description,
                        workspace=workspace)
        db.session.add(family)

        # Note that this commit will also include the workspace and the user
        # because they are related models
        db.session.commit()

        return family

    return _make_family


@pytest.fixture(scope='function')
def file_id():
    """Random file identifier as a uuid4"""
    return uuid4()


@pytest.fixture(scope='function')
def make_file(request):
    """Factory method to create small files as the ones received in a request"""

    class _NamedBytesIO(io.BytesIO):
        filename = 'some_name'

    def _make_file_contents(name='', path='', content=b''):
        if not content:
            content = os.urandom(64)
        if not name and not path:
            name = request.function.__name__
        instance = _NamedBytesIO(content)
        instance.filename = os.path.join(path, name)
        return instance

    return _make_file_contents


@pytest.fixture(scope='function')
def upload_file(make_file, user):
    """Factory method to upload files to a workspace"""
    _user = user

    def _upload_file(workspace, user=None, url=None, date=None, **kwargs):
        from app.api.data.file import create
        with mock.patch('app.api.data.file._upload_file', return_value=url or ''), \
             mock.patch('app.api.data.file._now', return_value=date or str(datetime.datetime.now(datetime.timezone.utc))):
            response, _ = create(id=workspace.id, file_content=make_file(**kwargs), user=user or _user)
            return response['id']

    return _upload_file


@pytest.fixture(scope='function')
def committed_file(request, db_session, make_family, file_id):
    """A file that is not associated to a workspace because it is committed"""
    base_family = make_family(name='base', version=1, workspace=None)
    other_family = make_family(name='other', version=1, workspace=None)
    base_metadata = Metadata(id_file=file_id, family=base_family, json={
        'id': str(file_id),
        'filename': request.function.__name__,
        'path': 'a/b/c',
        'size': 0,
        'checksum': 'd41d8cd98f00b204e9800998ecf8427e',
        'url': '',
        'date': '2019-02-03 16:30:11.350719+00:00',
    })
    other_metadata = Metadata(id_file=file_id, family=other_family, json={
        'id': str(file_id),
        'key': 'value',
    })

    db_session.add(base_family)
    db_session.add(other_family)
    db_session.add(base_metadata)
    db_session.add(other_metadata)
    db_session.commit()

    return {
        'id': str(file_id),
        'content': b'',  # content with md5 == 'd41d8cd98f00b204e9800998ecf8427e'
        'metadata': {
            'base': base_metadata.json,
            'other': other_metadata.json
        },
    }
