from logging.config import dictConfig

from flask.cli import AppGroup
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import click
import connexion

from config import config
from app.helpers.celery import Celery
from app.hacks import CustomResponseValidator
from app.middleware.debug import debug_request, debug_response


# Common objects usable accross the application
db = SQLAlchemy()
migrate = Migrate()
celery = Celery()


def create_app(config_name=None):
    # Use connexion to create and configure the initial application, but
    # we will use the Flask application to configure the rest
    connexion_app = connexion.App(__name__)
    flask_app = connexion_app.app
    # Update configuration according to the factory parameter or the FLASK_ENV
    # variable
    config_obj = config.get(config_name or flask_app.env)
    if config_obj is None:
        raise ValueError(f'Unknown configuration "{config_name}"')
    flask_app.config.from_object(config_obj)

    # Configure logging from the configuration object: I refuse to have the
    # logging configuration in another file (it's easier to manage)
    if 'LOGGING' in flask_app.config and flask_app.config['LOGGING']:
        dictConfig(flask_app.config['LOGGING'])

    # Database
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)

    # Celery (background tasks)
    flask_app.config['CELERY_BROKER_URL'] = flask_app.config['CELERY']['broker_url']
    celery.init_app(flask_app)
    # This is needed if flask-celery-helper is used instead of the
    # custom made Celery object in the app/helpers/celery.py helper script
    # celery.conf.update(flask_app.config['CELERY'])

    # Make configured Celery instance attach to Flask
    flask_app.celery = celery

    # APIs
    connexion_app.add_api('../openapi.yaml', strict_validation=True, validate_responses=True,
                          validator_map={'response': CustomResponseValidator})

    # Command-line interface tools
    from app.api.data.commands import init_buckets  # nopep8
    from app.commands import new_user  # nopep8

    data_cli = AppGroup('data', help='Quetzal data API operations')
    user_cli = AppGroup('users', help='Quetzal user operations')

    @user_cli.command('create')
    @click.argument('username')
    @click.argument('email')
    @click.password_option()
    def create_user_command(username, email, password):
        """ Create a new user """
        new_user(username, email, password)

    @data_cli.command('init')
    def data_init_command():
        """ Initialize data buckets """
        init_buckets()

    flask_app.cli.add_command(data_cli)
    flask_app.cli.add_command(user_cli)

    # Flask shell configuration
    from app.models import (
        Metadata, Family, User, Query, QueryDialect, Workspace, WorkspaceState
    )

    @flask_app.shell_context_processor
    def make_shell_context():
        return {
            # Handy reference to the database
            'db': db,
            # Add models here
            'User': User,
            'Metadata': Metadata,
            'Family': Family,
            'Query': Query,
            'QueryDialect': QueryDialect,
            'Workspace': Workspace,
            'WorkspaceState': WorkspaceState,
        }

    # Request/response logging
    flask_app.before_request(debug_request)
    flask_app.after_request(debug_response)

    return flask_app
