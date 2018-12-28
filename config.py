import logging
import os

# TODO: consider / add dot_env and load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # General Flask configuration
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'some-secret-key'

    # Logging
    LOGGING_LEVEL = logging.INFO
    LOGGING_FORMAT = '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(basedir, "app.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Celery configuration
    CELERY_BROKER_URL = 'amqp://guest:guest@rabbitmq:5672//'
    CELERY_RESULT_BACKEND = 'rpc://'

    # Quetzal-specific configuration
    QUETZAL_GCP_CREDENTIALS = os.environ.get('QUETZAL_APP_CREDENTIALS') or \
        os.path.join(basedir, 'conf', 'credentials.json')


class DevelopmentConfig(Config):
    DEBUG = True
    LOGGING_LEVEL = logging.DEBUG
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True

    # Database configuration (in-memory database)
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


class ProductionConfig(Config):
    pass


# Map of environment name -> configuration object
config = {
    'development': DevelopmentConfig,
    'testing': TestConfig,
    'production': ProductionConfig,
    'default': Config,
}
