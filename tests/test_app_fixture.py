# from app.models import User


def test_app_fixture(app):
    """Minimal test to verify the app fixture is loaded"""
    print(app)
    assert app is not None
    assert app.config['TESTING']

#
# # def test_mocking(app, mocker):
# #     """Minimal """
# #     mp = mocker.patch('os.listdir')
# #     print(mp)
# #     import os
# #     res = os.listdir('.')
# #     print(res)
# #
# #
# # def test_db(app, db):
# #     pass


def test_db_fixture(db):
    print(db)
    assert db is not None


def test_session_fixture(session):
    print(session)
    assert session is not None
