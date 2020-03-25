from quetzal.app.models import User
from quetzal.app.cli.users import _user_create


def test_user_create(app, db_session, make_random_str):
    """Test user creation"""
    username = 'tuc-' + make_random_str(size=8)
    email = 'tuc-' +  make_random_str(size=8) + '@quetz.al'
    password = make_random_str(size=8)
    _user_create(username, email, password)

    instance: User = User.query.filter_by(email=email).first()
    assert instance.username == username
    assert instance.email == email
    assert instance.check_password(password)
