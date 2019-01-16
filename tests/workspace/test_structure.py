import pytest

from sqlalchemy.exc import IntegrityError


def test_duplicate_workspace_db(user, make_workspace):
    """Two workspaces with the same user and name may not exist"""
    make_workspace(name='w1')
    with pytest.raises(IntegrityError):
        make_workspace(name='w1')
