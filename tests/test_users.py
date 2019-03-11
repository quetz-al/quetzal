from quetzal.app.models import User
from quetzal.app.cli.users import user_create


def test_new_user(db, db_session):
    """new_user function success"""
    email = 'username@example.com'
    user_obj = user_create('username', email, 'password')
    db_obj = User.query.filter_by(email=email).first()
    assert user_obj == db_obj
