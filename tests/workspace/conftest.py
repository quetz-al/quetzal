"""Common fixtures for workspace tests"""

import pytest

from app.models import Workspace, WorkspaceState


@pytest.fixture(scope='function')
def make_workspace(db, session, user):

    counter = 1
    workspaces = []

    def _make_workspace(name=None, state=None):
        nonlocal counter, workspaces
        # Create workspace on the database
        if name is None:
            name = f'fixture-workspace-{counter}'
            description = f'Fixture workspace #{counter} created by factory'
            counter += 1
        else:
            description = 'Fixture workspace created by factory'

        workspace = Workspace(name=name, description=description, owner=user)
        # Change the underlying state without respecting the transitions
        workspace._state = state or WorkspaceState.READY

        try:
            db.session.add(workspace)
            db.session.commit()
            w = Workspace.query.get(workspace.id)
            workspaces.append(w)
            return w

        except:
            db.session.rollback()
            raise

    yield _make_workspace

    db.session.rollback()  # In case there was an error that messed the db session
    for w in workspaces:
        db.session.delete(w)
    db.session.commit()
