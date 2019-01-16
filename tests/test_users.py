from app.commands import new_user
from app.models import User


def test_new_user(db, db_session):
    """new_user function success"""
    email = 'username@example.com'
    user_obj = new_user('username', email, 'password')
    db_obj = User.query.filter_by(email=email).first()
    assert user_obj == db_obj
