

def test_app_fixture(app):
    """Minimal test to verify the app fixture is loaded"""
    print(app)
    assert app is not None
    assert app.config['TESTING']


def test_db_fixture(db):
    print(db)
    assert db is not None


def test_session_fixture(session):
    print(session)
    assert session is not None
