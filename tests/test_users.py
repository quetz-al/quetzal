from quetzal.app.models import User
from quetzal.app.cli.users import user_create


def test_new_user(app, db_session):
    """new_user function success"""
    username = 'username'
    email = 'username@example.com'
    runner = app.test_cli_runner()
    result = runner.invoke(user_create, [username, email],
                           input='password\npassword\n')
    assert not result.exception
    db_obj = User.query.filter_by(email=email).first()
    assert db_obj.username == 'username' and db_obj.email == email
