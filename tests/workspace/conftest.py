"""Common fixtures for workspace tests"""
import pytest

from app.models import Family, Workspace, WorkspaceState


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
    workspace = make_workspace()
    return workspace


@pytest.fixture(scope="function")
def make_family(db, db_session, user, request):

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
