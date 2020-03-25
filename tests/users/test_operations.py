import pytest
from sqlalchemy.exc import IntegrityError

from quetzal.app.models import User


def test_user_create(make_user, make_random_str):
    """Test user creation"""

    username = make_random_str(size=8)
    email = make_random_str(size=8) + '@quetz.al'
    password = make_random_str(size=8)
    make_user(username=username, email=email, password=password)

    instance: User = User.query.filter_by(email=email).first()
    assert instance.username == username
    assert instance.email == email
    assert instance.check_password(password)


def test_duplicate_username(make_user, make_random_str):
    """Test that username is unique"""
    username = make_random_str(size=8)
    make_user(username=username)

    with pytest.raises(IntegrityError):
        make_user(username=username)


def test_duplicate_email(make_user, make_random_str):
    """Test that email is unique"""
    email = make_random_str(size=8) + '@quetz.al'
    make_user(email=email)

    with pytest.raises(IntegrityError):
        make_user(email=email)


def test_duplicate_token(db_session, make_user, make_random_str):
    """Test that a users' token is unique"""
    user1 = make_user()
    user2 = make_user()

    user1.get_token()
    db_session.commit()

    with pytest.raises(IntegrityError):
        user2.token = user1.token
        db_session.add(user2)
        db_session.commit()
