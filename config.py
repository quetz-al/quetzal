import copy
import os
import socket
import sys


# TODO: consider / add dot_env and load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))
try:
    hostname = socket.gethostname()
except:
    hostname = 'unknown'


def _ensure_dir_exists(dirname):
    os.makedirs(dirname, exist_ok=True)
    return dirname


def _remove_handler(log_config, name):
    # Make a new config
    new_config = copy.deepcopy(log_config)

    # Remove the handler
    del new_config['handlers'][name]

    # Remove references to that handler
    for logger_name in new_config['loggers']:
        handlers = new_config['loggers'][logger_name].get('handlers', [])
        if name in handlers:
            idx = handlers.index(name)
            new_config['loggers'][logger_name]['handlers'].pop(idx)
            # Clear when empty
            if not new_config['loggers'][logger_name]['handlers']:
                del new_config['loggers'][logger_name]['handlers']

    # Root handlers are in another place of the config
    root_handlers = new_config['root']['handlers']
    if name in root_handlers:
        idx = root_handlers.index(name)
        new_config['root']['handlers'].pop(idx)

    return new_config


_is_celery_worker = (
    len(sys.argv) > 0 and
    sys.argv[0].endswith('celery') and
    'worker' in sys.argv
)


class Config:
    # General Flask configuration
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'some-secret-key'
    SERVER_NAME = (
        os.environ.get('SERVER_NAME') or 'local.quetz.al'
    ).split(',')[0]

    # Logging
    LOG_DIR = _ensure_dir_exists(os.environ.get('LOG_DIR') or
                                 os.path.join(basedir, 'logs', 'app'))
    LOGGING = {
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(levelname)s %(name)s %(asctime)s %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'detailed': {
                'format': '%(asctime)s %(levelname)s %(name)s.%(funcName)s:- %(message)s '
                          '[in %(pathname)s:%(lineno)d]',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'GDPR_format': {
                '()': 'syslog_rfc5424_formatter.RFC5424Formatter',
            },
            # A formatter for celery tasks that includes task_name and task_id
            'celery_formatter': {
                '()': 'celery.app.log.TaskFormatter',
                'format': '%(levelname)s %(asctime)s [%(task_name)s(%(task_id)s)] '
                          '%(name)s.%(funcName)s:%(lineno)s- %(message)s',
            }
        },
        'handlers': {
            # The default logging on console
            'console': {
                'level': 'INFO',  # on info so that the console is rather brief
                'class': 'logging.StreamHandler',
                'formatter': 'default',
            },
            # A more detailed logging file for debugging
            'file': {
                'level': 'DEBUG',  # on debug so that the file has much more details
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'detailed' if not _is_celery_worker else 'celery_formatter',
                'filename': os.path.join(LOG_DIR,
                                         f'worker-{hostname}.log' if _is_celery_worker
                                         else f'app-{hostname}.log'),
                'maxBytes': 10 * (1 << 20),  # 10 Mb
                'backupCount': 100,
            },
            # A separate logging file for GRPD request tracking
            'GDPR_file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'formatter': 'GDPR_format',
                'filename': os.path.join(LOG_DIR, f'GDPR-{hostname}.log'),
                'when': 'midnight',
                'utc': True,
            }
            # TODO: add email handler for errors
        },
        'loggers': {
            'quetzal.app.middleware.gdpr': {
                'level': 'DEBUG',  # Keep this on debug
                'handlers': ['GDPR_file'],
            },
            # 'quetzal.app.api.data.tasks': {
            #     'level': 'DEBUG',
            #     'handlers': ['file_worker']
            # },
            'quetzal.app.middleware.debug': {
                'level': 'INFO',
            },
            # apscheduler is quite verbose
            'apscheduler': {
                'level': 'WARNING',
            },
            # Some Python internal loggers that are too verbose
            'parso': {
                'level': 'WARNING',
            },
            # Connexion is also very verbose but we want to put it on DEBUG sometimes...
            'connexion': {
                'level': 'DEBUG',
            },
            'openapi_spec_validator': {
                'level': 'INFO',
            },
        },
        'root': {
            'level': 'DEBUG',  # on debug so that the file has all details
            'handlers': ['console', 'file'],
        },
        'disable_existing_loggers': False,
    }

    # Database configuration
    SQLALCHEMY_DATABASE_URI = (
            'postgresql://' +
            # Sole difference with the production config: there is a default
            # value for the user and password (it does not fail if not set)
            os.environ.get('DB_USERNAME', 'db_user') + ':' +
            os.environ.get('DB_PASSWORD', 'db_password') + '@' +
            os.environ.get('DB_HOST', 'db') + ':' +
            os.environ.get('DB_PORT', '5432') + '/' +
            os.environ.get('DB_DATABASE', 'quetzal')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_BINDS = {
        'read_only_bind':
            'postgresql://' +
            os.environ.get('DB_RO_USERNAME', 'db_ro_user') + ':' +
            os.environ.get('DB_RO_PASSWORD', 'db_ro_password') + '@' +
            os.environ.get('DB_HOST', 'db') + ':' +
            os.environ.get('DB_PORT', '5432') + '/' +
            os.environ.get('DB_DATABASE', 'quetzal')
    }

    # Celery configuration
    # Note that from Celery 4.0, configuration keys are in lowercase. This is
    # why the Celery configuration is set in this inner dictionary
    CELERY = {
        'broker_url': 'amqp://guest:guest@' +
                      os.environ.get('RABBITMQ_HOST', 'rabbitmq') + ':' +
                      os.environ.get('RABBITMQ_PORT', '5672') +
                      '//',
        # Due to an issue on the rpc backend, there is an infinite loop that
        # blocks the scheduling of tasks. Removing result_backend as we have
        # no use for it right now.
        'result_backend': None,  # 'rpc://',
        'include': ['quetzal.app.api.data.tasks'],
        'broker_transport_options': {
            'max_retries': 3,
            'interval_start': 0,
            'interval_step': 0.2,
            'interval_max': 0.2,

        },
        # 'worker_log_format': LOGGING['formatters']['default']['format'],
        # 'worker_task_log_format': LOGGING['formatters']['celery_tasks']['format'],
        'worker_hijack_root_logger': False,
    }

    # Quetzal-specific configuration
    # ------------------------------
    # data storage: 'GCP' for Google Cloud Platform, 'file' for local storage
    QUETZAL_DATA_STORAGE = os.environ.get('QUETZAL_DATA_STORAGE', 'GCP')
    QUETZAL_BACKGROUND_JOBS = bool(os.environ.get('QUETZAL_BACKGROUND_JOBS', False))

    # Quetzal-GCP storage configuration
    QUETZAL_GCP_CREDENTIALS = os.environ.get('QUETZAL_GCP_CREDENTIALS') or \
        os.path.join(basedir, 'conf', 'credentials.json')
    QUETZAL_GCP_DATA_BUCKET = os.environ.get('QUETZAL_GCP_DATA_BUCKET') or \
        'gs://quetzal-dev-data'
    QUETZAL_GCP_BACKUP_BUCKET = os.environ.get('QUETZAL_GCP_BACKUP_BUCKET') or \
        'gs://quetzal-dev-backups'
    QUETZAL_GCP_BUCKET_PREFIX = os.environ.get('QUETZAL_GCP_BUCKET_PREFIX') or \
        'quetzal-ws'

    # Quetzal-file storage configuration
    QUETZAL_FILE_DATA_DIR = os.environ.get('QUETZAL_FILE_DATA_DIR') or '/data'
    QUETZAL_FILE_USER_DATA_DIR = os.environ.get('QUETZAL_FILE_USER_DATA_DIR') or '/workspaces'

    def __init__(self):
        # Dynamic properties: configuration elements that must change according
        # to some information that is only available when Flask is instantiated

        # Logs: do not use the same filename for worker and app. We can only
        # know this if we detect we are in a celery program or not.
        if _is_celery_worker:
            # Remove the file handler
            # self.LOGGING = _remove_handler(self.LOGGING, 'file')
            # Remove the GDPR handler
            self.LOGGING = _remove_handler(self.LOGGING, 'GDPR_file')


class DevelopmentConfig(Config):
    """ Configuration for regular development.

    Use for a docker-compose development enviroment.
    """
    DEBUG = True
    JSON_SORT_KEYS = False


class StagingConfig(Config):
    """ Configuration for a staging server.

    Use for servers deployed to GCP, an environment that resembles production.

    """


class TestConfig(Config):
    """Configuration for unit tests

    This particular class conecenrs an environment that has access to all other
    services (rabbitmq, db, ...). Normally, this should run as a docker-compose
    service.
    """
    TESTING = True

    # Logging
    # For unit tests, let pytest handle the logging. For better readability, we
    # are minimizing the connexion and openapi logs because they are very
    # verbose
    LOGGING = {
        'version': 1,
        'loggers': {
            'connexion': {
                'level': 'INFO',
            },
            'openapi_spec_validator': {
                'level': 'INFO',
            }
        },
        # Important: leave the root logger alone, since pytest configures it
        'incremental': True,
    }

    # Database configuration
    SQLALCHEMY_DATABASE_URI = (
            'postgresql://' +
            os.environ.get('DB_USERNAME', 'db_user') + ':' +
            os.environ.get('DB_PASSWORD', 'db_password') + '@' +
            os.environ.get('DB_HOST', 'db') + ':' +
            os.environ.get('DB_PORT', '5432') + '/' +
            os.environ.get('DB_DATABASE', 'unittests')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_BINDS = {
        'read_only_bind':
            'postgresql://' +
            os.environ.get('DB_RO_USERNAME', 'db_ro_user') + ':' +
            os.environ.get('DB_RO_PASSWORD', 'db_ro_password') + '@' +
            os.environ.get('DB_HOST', 'db') + ':' +
            os.environ.get('DB_PORT', '5432') + '/' +
            os.environ.get('DB_DATABASE', 'unittests')
    }

    # Quetzal-specific configuration
    QUETZAL_GCP_CREDENTIALS = None
    QUETZAL_GCP_DATA_BUCKET = 'gs://quetzal-unit-tests'


class LocalTestConfig(TestConfig):
    """Configuration for local unit tests

    Local unit tests are run outside the docker-compose structure, useful for
    tests that need debugging.
    """

    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'postgresql://db_user:db_password@localhost:5432/unittests'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_BINDS = {
        'read_only_bind': 'postgresql://db_ro_user:db_ro_password@localhost:5432/unittests'
    }

    # Celery configuration on eager mode
    CELERY = {
        'broker_url': 'memory',
        'include': ['quetzal.app.api.data.tasks'],
        'broker_transport_options': {
            'max_retries': 3,
            'interval_start': 0,
            'interval_step': 0.2,
            'interval_max': 0.2,

        },
        'task_always_eager': True,
        'task_eager_propagates': True,
    }


class ProductionConfig(Config):
    pass


# Map of environment name -> configuration object
config = {
    'development': DevelopmentConfig,
    'tests': TestConfig,
    'local-tests': LocalTestConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
