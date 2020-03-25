# pytest fixtures for flask, sqlalchemy and celery, based on
# https://github.com/sunscrapers/flask-boilerplate/blob/master/tests/conftest.py

import logging
import os
import unittest.mock

import pytest

from config import config
from quetzal.app import create_app
from quetzal.app import db as _db
# from quetzal.app.models import User


logger = logging.getLogger(__name__)


# =============================================================================
# Global fixtures, aka 'session-wide' fixtures
# =============================================================================

@pytest.fixture(scope='session')
def app_config_name():
    return os.environ.get('FLASK_ENV') or 'tests'


@pytest.fixture(scope='session')
def app_config(app_config_name):
    config_class = config.get(app_config_name)
    config_instance = config_class()
    return config_instance


@pytest.fixture(scope='session', autouse=False)
def app(app_config_name):
    """ A session-wide, configured application

    The configuration of the application will depend on the FLASK_ENV
    environment variable. If this variable is not set, the "tests"
    configuration will be used.
    """
    logger.debug('Creating app from env=%s', app_config_name)
    _app = create_app(app_config_name)
    with _app.app_context():
        yield _app
        logger.debug('Tearing down application')


@pytest.fixture(scope='session', autouse=False)
def db(app, request):
    """ Returns a session-wide initialized db """
    if app.config['TEST_USE_DOCKER_COMPOSE']:
        request.getfixturevalue('db_service')

    logger.debug('Creating database structure')
    # Drop anything that may have been added before and was not
    # deleted for some reason
    try:
        _db.drop_all()
    except:
        pass
    # Create all tables
    _db.create_all()

    # logger.debug('Creating database connection')
    # connection = _db.engine.connect()
    # transaction = connection.begin()
    # with unittest.mock.patch('quetzal.app.db.get_engine') as get_engine_mock:
    #     get_engine_mock.return_value = connection
    #     try:
    #         yield _db
    #     finally:
    #         logger.info('Tearing down database connection')
    #         _db.session.remove()
    #         transaction.rollback()
    #         connection.close()
    yield _db

    logger.debug('Tearing down database connection')
    _db.session.remove()

    # Drop all tables
    logger.debug('Dropping all tables')
    _db.drop_all()


@pytest.fixture(scope="session")
def url(app_config, request):
    """An URL from a responsive Quetzal over HTTPS service.

    This service is running on docker-compose when the TEST_USE_DOCKER_COMPOSE
    configuration variable (on config.py) is set. The docker-compose instance
    is created as a session fixture.
    When the TEST_USE_DOCKER_COMPOSE is not set, this URL be an address to
    localhost.
    """
    _ = request.getfixturevalue('web_service')
    if app_config.TEST_USE_DOCKER_COMPOSE:
        docker_ip = request.getfixturevalue('docker_ip')
        url = f'https://{docker_ip}'
    else:
        url = 'https://localhost'
    return url


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


# @pytest.fixture(scope='function')
# def user(app, db, db_session, request):
#     """ Returns a *function*-wide user """
#     counter = 0
#     username = f'u-{request.function.__name__}_{counter:03}'
#     email = f'{username}@example.com'
#     # Try a new user until there is a new one
#     while User.query.filter_by(email=email).first() is not None:
#         counter += 1
#         username = f'{username[:-4]}_{counter:03}'
#         email = f'{username}@example.com'
#         if counter >= 1000:
#             raise RuntimeError('Too many users')
#
#     _user = User(username=username, email=email)
#     db_session.add(_user)
#     db_session.commit()
#     return _user
