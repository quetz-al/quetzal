def test_workspace_factory_fixture(make_workspace, db_session, user):
    assert make_workspace() is not None


def test_workspace_fixture(workspace):
    assert workspace is not None
