import pytest

from sqlalchemy.exc import IntegrityError

from app.models import Workspace


def test_duplicate_workspace_db(db, workspace, db_session):
    """Two workspaces with the same user and name may not exist"""
    duplicate = Workspace(name=workspace.name, owner=workspace.owner)
    with pytest.raises(IntegrityError):
        db.session.add(duplicate)
        db.session.commit()
