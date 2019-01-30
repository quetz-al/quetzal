import os

# TODO: consider / add dot_env and load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # General Flask configuration
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'some-secret-key'

    # Logging
    LOG_DIR = os.environ.get('LOG_DIR') or os.path.join(basedir, 'logs')
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
                'level': 'DEBUG',  # on info so that the console is rather brief
                'class': 'logging.StreamHandler',
                'formatter': 'default',
            },
            # A more detailed logging file for debugging
            'file': {
                'level': 'DEBUG',  # on debug so that the file has much more details
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'detailed',
                'filename': os.path.join(LOG_DIR, 'quetzal.log'),
                'maxBytes': 10 * (1 << 20),  # 10 Mb
                'backupCount': 100,
            },
            # A separate logging file for the celery tasks
            'file_worker': {
                'level': 'DEBUG',  # like the file handler but on another file
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'celery_formatter',
                'filename': os.path.join(LOG_DIR, 'worker.log'),
                'maxBytes': 10 * (1 << 20),  # 10 Mb
                'backupCount': 100,
            },
            # TODO: add email handler for errors
        },
        'loggers': {
            'app.api.data.tasks': {
                'level': 'DEBUG',
                'handlers': ['file_worker']
            },
            'app.middleware.debug': {
                'level': 'INFO',
            },
            # Some Python internal loggers that are too verbose
            'parso': {
                'level': 'WARNING',
            },
            # ...
            'connexion': {
                'level': 'INFO',
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
                      os.environ.get('RABBITMQ_HOST', 'rabbitmq') +
                      ':5672//',
        'result_backend': 'rpc://',
        'include': ['app.api.data.tasks'],
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
    QUETZAL_GCP_CREDENTIALS = os.environ.get('QUETZAL_APP_CREDENTIALS') or \
        os.path.join(basedir, 'conf', 'credentials.json')
    QUETZAL_GCP_DATA_BUCKET = os.environ.get('QUETZAL_GCP_DATA_BUCKET') or \
        'gs://quetzal-dev-data'


class DevelopmentConfig(Config):
    DEBUG = True
    JSON_SORT_KEYS = False
    SERVER_NAME = 'localhost:5000'


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
        'include': ['app.api.data.tasks'],
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
    'production': ProductionConfig,
    'default': Config,
}
