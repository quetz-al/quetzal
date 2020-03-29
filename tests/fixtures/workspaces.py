from typing import Dict

import pytest
from sqlalchemy import func

from quetzal.app.models import Family, Workspace, WorkspaceState


@pytest.fixture(scope='function')
def make_workspace(app, db_session, make_random_str, make_user, request):
    """Factory fixture to create Quetzal workspaces

    Using this fixture does not trigger a celery task
    """
    counter = 0
    prefix = f'w-{request.function.__name__}_{make_random_str(4)}'

    def factory(*, name=None, description=None, families=None, temporary=False, state=None, user=None):
        nonlocal counter
        counter += 1

        name = name or f'{prefix}-{counter}'
        description = description or f'Fixture workspace #{counter} created by factory'
        families = families or {'base': None}
        state = state or WorkspaceState.READY
        user = user or make_user()

        workspace = Workspace(name=name, description=description, temporary=temporary, owner=user)
        workspace._state = state  # bypass transition verification
        db_session.add(workspace)

        # Add families
        for name, version in families.items():
            family = Family(name=name, version=version, workspace=workspace)
            db_session.add(family)
        db_session.commit()

        return workspace

    return factory


@pytest.fixture(scope='function')
def workspace(make_workspace):
    """ A simple Quetzal workspace """
    return make_workspace()


@pytest.fixture(scope='function')
def missing_workspace_id(db_session):
    """A workspace id from a workspace that does not exist

    Warning: if a workspace is created after this fixture is created, then it
    is highly likely that the value now corresponds to an existing workspace
    """
    # Get the latest workspace id in order to request one that does not exist
    max_id = db_session.query(func.max(Workspace.id)).scalar() or 0
    # the next id should not exist
    return max_id + 1


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
