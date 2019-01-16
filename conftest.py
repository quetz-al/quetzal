# pytest fixtures for flask, sqlalchemy and celery, based on
# https://github.com/sunscrapers/flask-boilerplate/blob/master/tests/conftest.py

import logging
import os
import unittest.mock

import pytest

from app import create_app
from app import db as _db
from app.models import User


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
    logger.info('Creating app from env=%s', config_name)
    _app = create_app(config_name)
    with _app.app_context():
        yield _app


@pytest.fixture(scope='session', autouse=True)
def db(app):
    """ Returns a session-wide initialized db """
    # Drop anything that may have been added before and was not
    # deleted for some reason
    _db.drop_all()
    # Create all tables
    _db.create_all()

    connection = _db.engine.connect()
    transaction = connection.begin()
    with unittest.mock.patch('app.db.get_engine') as get_engine_mock:
        get_engine_mock.return_value = connection
        try:
            yield _db
        finally:
            _db.session.remove()
            transaction.rollback()
            connection.close()

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
    db.session.begin_nested()
    yield db.session
    db.session.rollback()


@pytest.fixture(scope='function')
def user(app, db, session):
    """ Returns a *function*-wide user """
    _user = User(username='user', email='user@example.com')
    session.add(_user)
    session.commit()
    yield _user
