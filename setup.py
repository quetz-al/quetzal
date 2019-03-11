# http://flask.pocoo.org/docs/1.0/patterns/packages/

from setuptools import setup

import versioneer


setup(
    name='quetzal',
    packages=['quetzal'],
    include_package_data=True,
    install_requires=[
        'Flask',
        'werkzeug',
        'Flask-Login',
        'Flask-Principal',
        'connexion',
        'celery',
        'kombu',
        'Flask-Celery-Helper',
        'SQLAlchemy',
        'Flask-SQLAlchemy',
        'Flask-Migrate',
        'alembic',
        'psycopg2-binary',
        'sqlparse',
        'requests',
        'Click',
        'syslog-rfc5424-formatter',
        'apscheduler',
        'gunicorn',
        'google-cloud-storage',
    ],
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
)
