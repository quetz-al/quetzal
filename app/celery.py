"""Improved version of the celery object of flask_celery_helper package

The original flask_celery.Celery object has a bug where the context
is pushed during unit tests. This file extends and rewrites the
related code to avoid this bug.

This bug has been documented on:
https://github.com/Robpol86/Flask-Celery-Helper/issues/23

"""

from celery import _state, Celery as CeleryGrandParentClass
from flask_celery import _CeleryState, Celery as CeleryParentClass


class Celery(CeleryParentClass):
    def init_app(self, app):
        """Actual method to read celery settings from app configuration and initialize the celery instance.

        Positional arguments:
        app -- Flask application instance.
        """
        _state._register_app = self.original_register_app  # Restore Celery app registration function.
        if not hasattr(app, 'extensions'):
            app.extensions = dict()
        if 'celery' in app.extensions:
            raise ValueError('Already registered extension CELERY.')
        app.extensions['celery'] = _CeleryState(self, app)

        # Get the celery config
        celery_config = app.config.get('CELERY', {})

        # Instantiate celery and read config.
        CeleryGrandParentClass.__init__(self, app.import_name, broker=celery_config['broker_url'])

        # Set result backend default.
        if 'result_backend' in celery_config:
            self._preconf['CELERY_RESULT_BACKEND'] = celery_config['result_backend']

        self.conf.update(celery_config)
        task_base = self.Task

        # Add Flask app context to celery instance.
        class ContextTask(task_base):
            """Celery instance wrapped within the Flask app context."""
            def __call__(self, *_args, **_kwargs):
                if app.config['TESTING']:
                    with app.test_request_context():
                        return task_base.__call__(self, *_args, **_kwargs)
                with app.app_context():
                    return task_base.__call__(self, *_args, **_kwargs)
        setattr(ContextTask, 'abstract', True)
        setattr(self, 'Task', ContextTask)
