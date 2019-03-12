# http://flask.pocoo.org/docs/1.0/patterns/packages/

from setuptools import setup, find_packages

import versioneer


authors = [
    ('David Ojeda', 'david@dojeda.com'),
]
author_names = ', '.join(tup[0] for tup in authors)
author_emails = ', '.join(tup[1] for tup in authors)

setup(
    name='quetzal',
    packages=find_packages(exclude=['docs', 'migrations', 'tests']),
    namespace_packages=['quetzal'],
    include_package_data=True,
    python_requires='>=3.6, ~=3.7',
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
    author=author_names,
    author_email=author_emails,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Flask',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Database',
        'Topic :: Scientific/Engineering',
        'Topic :: System :: Archiving',
    ],
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    zip_safe=False,
)
