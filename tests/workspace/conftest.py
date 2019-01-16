"""Common fixtures for workspace tests"""
import unittest.mock

import pytest

from app.models import User, Workspace, WorkspaceState


@pytest.fixture(scope='session')
def tester_user(app, db):
    u = User(username='workspace-tester', email='workspace-tester@example.com')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture(scope='session')
def workspace(app, db, tester_user):
    ws = Workspace(name='workspace-tests',
                   description='Fixture workspace for unit tests',
                   owner=tester_user)
    db.session.add(ws)
    db.session.commit()
    return ws


@pytest.fixture(scope='function')
def make_workspace(db, db_session, tester_user):

    counter = 1

    def _make_workspace(name=None, state=None, owner=None):
        nonlocal counter
        # Create workspace on the database
        if name is None:
            name = f'fixture-workspace-{counter}'
            description = f'Fixture workspace #{counter} created by factory'
            counter += 1
        else:
            description = 'Fixture workspace created by factory'

        workspace = Workspace(name=name, description=description, owner=owner or tester_user)
        # Change the underlying state without respecting the transitions
        workspace._state = state or WorkspaceState.READY

        db.session.add(workspace)
        db.session.commit()

        return workspace

    yield _make_workspace
