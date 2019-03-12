import os
from logging.config import dictConfig


from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask.helpers import get_env
from flask_migrate import Migrate
from flask_principal import Principal, identity_loaded
from flask_sqlalchemy import SQLAlchemy
import connexion

from config import config
from .helpers.celery import Celery
from .hacks import CustomResponseValidator
from .middleware.debug import debug_request, debug_response
from .middleware.gdpr import gdpr_log_request
from .middleware.headers import HttpHostHeaderMiddleware
from .security import load_identity


# Version with versioneer
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions


# Common objects usable across the application
db = SQLAlchemy()
migrate = Migrate()
celery = Celery()
principal = Principal(use_sessions=False)
scheduler = BackgroundScheduler()
scheduler.start()


def create_app(config_name=None):
    # Obtain the configuration according to the factory parameter or the
    # FLASK_ENV variable
    #
    # Note:
    # Remark that the constructor is called explicitly because there are some
    # refinements to the configuration that are not known until the application
    # is executed
    config_obj = config.get(config_name or get_env())()
    if config_obj is None:
        raise ValueError(f'Unknown configuration "{config_name}"')

    # Configure logging as soon as possible... even before Flask because the
    # Flask object is created by Connexion, who already logs a lot!
    # The logging configuration is declared in the config object, because I
    # refuse to have the logging configuration in another file
    # (it's easier to manage)
    if hasattr(config_obj, 'LOGGING') and config_obj.LOGGING:
        dictConfig(config_obj.LOGGING)

    # Use connexion to create and configure the initial application, but
    # we will use the Flask application to configure the rest
    connexion_app = connexion.App(__name__, options={"swagger_ui": False})
    flask_app = connexion_app.app

    # Update Flask configuration
    flask_app.config.from_object(config_obj)

    # Database
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)

    # Celery (background tasks)
    flask_app.config['CELERY_BROKER_URL'] = flask_app.config['CELERY']['broker_url']
    celery.init_app(flask_app)
    # This is needed if flask-celery-helper is used instead of the
    # custom made Celery object in the app/helpers/celery.py helper script:
    # celery.conf.update(flask_app.config['CELERY'])

    # Make configured Celery instance attach to Flask
    flask_app.celery = celery

    # APIs
    from . import __version__
    connexion_app.add_api('../../openapi.yaml',
                          arguments={'version': __version__},
                          strict_validation=True, validate_responses=True,
                          validator_map={'response': CustomResponseValidator})

    # Other extensions
    from .redoc import bp as redoc_bp
    flask_app.register_blueprint(redoc_bp)
    from .routes import static_bp
    flask_app.register_blueprint(static_bp)

    # Principals
    principal.init_app(flask_app)
    identity_loaded.connect_via(flask_app)(load_identity)

    # Command-line interface tools
    from .cli import quetzal_cli
    flask_app.cli.add_command(quetzal_cli)

    # Flask shell configuration
    from .models import (
        User, Role,
        Metadata, Family, MetadataQuery, QueryDialect, Workspace, WorkspaceState
    )

    @flask_app.shell_context_processor
    def make_shell_context():
        return {
            # Handy reference to the database
            'db': db,
            # Add models here
            'User': User,
            'Role': Role,
            'Metadata': Metadata,
            'Family': Family,
            'MetadataQuery': MetadataQuery,
            'QueryDialect': QueryDialect,
            'Workspace': Workspace,
            'WorkspaceState': WorkspaceState,
        }

    # Request/response logging
    # GDPR logging
    flask_app.before_request(gdpr_log_request)

    # Debugging of requests and responses
    if flask_app.debug:
        flask_app.before_request(debug_request)
        flask_app.after_request(debug_response)

    # Other middleware
    proxied = HttpHostHeaderMiddleware(flask_app.wsgi_app, server=flask_app.config['SERVER_NAME'])
    flask_app.wsgi_app = proxied

    # Install recurrent jobs (not through celery):
    #
    # Note:
    # We have the specific need to run some background tasks that **must** run
    # on all instances of the Flask application and celery workers. This is
    # something that cannot be implemented with celery. This could be
    # implemented through cron, but needs some local configuration and since
    # this app runs within Docker, it is discouraged to run more than one
    # process per Docker container.
    # For these reasons, we are using apscheduler as a Python replacement of a
    # cron scheduler.
    #
    # The condition below is to avoid repeated scheduling by Flask, specially
    # when the --no-reload option is not used (like in development mode),
    # because Flask runs two threads and each one calls this create_app
    # factory method.
    if (flask_app.config['QUETZAL_BACKGROUND_JOBS'] and
            not flask_app.testing and
            os.environ.get('WERKZEUG_RUN_MAIN') is None):

        from quetzal.app.background import hello, backup_logs
        # Simple job to know what's alive every 10 minutes
        scheduler.add_job(hello, trigger='interval', seconds=600)
        # Backup logs at midnight + 5 minutes so that the timed rolling logs do their rollover
        scheduler.add_job(backup_logs, trigger=CronTrigger(hour=0, minute=5),
                          args=(flask_app,), misfire_grace_time=3600*6)

    return flask_app
