"""Common fixtures for workspace tests"""
import unittest.mock

import pytest

from app.models import Workspace, WorkspaceState


@pytest.fixture(scope='function')
def make_workspace(db, db_session, user, request):

    counter = 1

    def _make_workspace(name=None, state=None, owner=None):
        nonlocal counter
        # Create workspace on the database
        if name is None:
            name = f'w-{request.function.__name__}-{counter}'
            description = f'Fixture workspace #{counter} created by factory'
            counter += 1
        else:
            description = 'Fixture workspace created by factory'

        workspace = Workspace(name=name, description=description, owner=owner or user)
        # Change the underlying state without respecting the transitions
        workspace._state = state or WorkspaceState.READY

        db.session.add(workspace)
        # Note that this commit will also include the user because it is a
        # related model.
        db.session.commit()

        return workspace

    yield _make_workspace


@pytest.fixture(scope='function')
def workspace(make_workspace):
    workspace = make_workspace()
    return workspace
