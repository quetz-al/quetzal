def test_workspace_factory_fixture(make_workspace, db_session, user):
    """Workspace factory fixture works"""
    assert make_workspace() is not None


def test_workspace_fixture(workspace):
    """Workspace fixture works"""
    assert workspace is not None
