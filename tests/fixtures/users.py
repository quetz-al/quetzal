import pytest

from quetzal.app.models import User


@pytest.fixture(scope='function')
def make_user(db_session, make_random_str, request):
    """Factory fixture to create Quetzal users"""
    counter = 0
    prefix = f'u-{request.function.__name__}_{make_random_str(4)}'

    def factory(*, username=None, email=None, password=None):
        nonlocal counter
        counter += 1

        username = username or f'{prefix}_{counter}'
        email = email or f'{prefix}_{counter}@quetz.al'
        user = User(username=username, email=email)
        if password is not None:
            user.set_password(password)

        db_session.add(user)
        db_session.commit()
        return user

    return factory


@pytest.fixture(scope='function')
def user(make_user):
    """ A simple Quetzal user """
    return make_user()
