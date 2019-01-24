"""Tests on correct fixtures"""


def test_app_fixture(app):
    """app fixture is loaded"""
    assert app is not None
    assert app.config['TESTING']


def test_db_fixture(db):
    """db fixture is loaded"""
    assert db is not None


def test_session_fixture(db_session):
    """db_session fixture is loaded"""
    assert db_session is not None
