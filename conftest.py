# pytest fixtures for flask, sqlalchemy and celery, based on
# https://github.com/sunscrapers/flask-boilerplate/blob/master/tests/conftest.py

import logging
import os
import pytest


from app import create_app
from app import db as _db
from app.commands import new_user


logger = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def app():
    """ Returns session-wide, configured application

    The configuration of the application will depend on the FLASK_ENV
    environment variable. If this variable is not set, the "tests"
    configuration will be used.
    """
    config_name = os.environ.get('FLASK_ENV', 'tests')
    logger.info('Creating app from env=%s', config_name)
    _app = create_app(config_name)
    with _app.app_context():
        yield _app


@pytest.fixture(scope='session')
def db(app):
    """ Returns a session-wide initialized db

    Note that any function that needs to add or manipulate database
    objects (directly or indirectly) *must* use the `session` fixture.
    If you use the `db` fixture, the unit test will hang when destroying
    the `db` fixture because there will be a dangling database session.
    """
    # Drop anything that may have been added before and was not
    # deleted for some reason
    _db.drop_all()
    # Create all tables
    _db.create_all()
    yield _db
    # Drop any changes on the database
    _db.drop_all()


@pytest.fixture(scope='function')
def session(db):
    """ Returns a function-wide database session

    Note that any function that needs to add or manipulate database
    objects (directly or indirectly) *must* use this fixture. If you
    use the `db` fixture, the unit test will hang when destroying the
    `db` fixture because there will be a dangling database session.
    """
    connection = db.engine.connect()
    transaction = connection.begin()

    options = dict(bind=connection)
    session = db.create_scoped_session(options=options)

    db.session = session
    yield session

    transaction.rollback()
    connection.close()
    session.remove()


@pytest.fixture(scope='function')
def user(app, db, session):
    """ Returns a function-wide user """
    _user = new_user('user1', 'test@example.com', 'secret_password')
    return _user
