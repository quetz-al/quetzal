# pytest fixtures for flask, sqlalchemy and celery, based on
# https://github.com/sunscrapers/flask-boilerplate/blob/master/tests/conftest.py

import logging
import os
import unittest.mock

import pytest

from quetzal.app import create_app
from quetzal.app import db as _db
from quetzal.app.models import User


logger = logging.getLogger(__name__)


# =============================================================================
# Global fixtures, aka 'session-wide' fixtures
# =============================================================================

@pytest.fixture(scope='session', autouse=True)
def app():
    """ A session-wide, configured application

    The configuration of the application will depend on the FLASK_ENV
    environment variable. If this variable is not set, the "tests"
    configuration will be used.
    """
    config_name = os.environ.get('FLASK_ENV', 'tests')
    logger.debug('Creating app from env=%s', config_name)
    _app = create_app(config_name)
    with _app.app_context():
        yield _app
        logger.debug('Tearing down application')


@pytest.fixture(scope='session', autouse=True)
def db(app):
    """ Returns a session-wide initialized db """
    logger.debug('Creating database structure')
    # Drop anything that may have been added before and was not
    # deleted for some reason
    _db.drop_all()
    # Create all tables
    _db.create_all()

    logger.debug('Creating database connection')
    connection = _db.engine.connect()
    transaction = connection.begin()
    with unittest.mock.patch('app.db.get_engine') as get_engine_mock:
        get_engine_mock.return_value = connection
        try:
            yield _db
        finally:
            logger.info('Tearing down database connection')
            _db.session.remove()
            transaction.rollback()
            connection.close()

    logger.debug('Dropping all tables')
    # Drop all tables
    _db.drop_all()


# =============================================================================
# Global fixtures, aka 'function-specific' fixtures
# =============================================================================

@pytest.fixture(scope='function')
def db_session(db):
    """ Returns a *function*-wide database session

    Use this fixture for any test that should clean any objects created in it.
    In particular, if a test leaves the session in an unusable state, such as
    when a session.commit fails.
    """
    logger.debug('Creating database session')
    db.session.begin_nested()
    yield db.session

    logger.debug('Tearing down database session')
    db.session.rollback()


@pytest.fixture(scope='function')
def user(app, db, db_session, request):
    """ Returns a *function*-wide user """
    counter = 0
    username = f'u-{request.function.__name__}_{counter:03}'
    email = f'{username}@example.com'
    # Try a new user until there is a new one
    while User.query.filter_by(email=email).first() is not None:
        counter += 1
        username = f'{username[:-4]}_{counter:03}'
        email = f'{username}@example.com'
        if counter >= 1000:
            raise RuntimeError('Too many users')

    _user = User(username=username, email=email)
    db_session.add(_user)
    db_session.commit()
    return _user
