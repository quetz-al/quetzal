import pytest

from sqlalchemy.exc import IntegrityError

from quetzal.app.models import Workspace


def test_duplicate_workspace_db(db, make_workspace, db_session, user):
    """Two workspaces with the same user and name may not exist"""
    workspace = make_workspace()
    duplicate = Workspace(name=workspace.name, owner=workspace.owner)
    with pytest.raises(IntegrityError):
        db.session.add(duplicate)
        db.session.commit()
