import base64
import logging


logger = logging.getLogger(__name__)


def log_request():
    from flask import request
    from app.models import User
    log_entry = {
        'headers': {
            key: value
            for key, value in request.headers
        },
        'environment': {
            key: repr(value)
            for key, value in request.environ.items()
        },
        'url': request.url,
        'full_path': request.full_path,
        'method': request.method,
        'data': request.data,
        'user': None,
    }
    user = None

    if 'Authorization' in request.headers:
        try:
            auth_type, content = request.headers['Authorization'].split(None, 1)
            if auth_type.lower() == 'basic':
                username, _ = base64.b64decode(content).decode('latin1').split(':', 1)
                user = User.query.get(username=username).first()
            elif auth_type.lower() == 'bearer':
                user = User.check_token(content)

            log_entry['headers']['Authorization'] = f'{auth_type} ...REDACTED...'

        except:
            logger.debug('Could not determine user', exc_info=True)

    if 'HTTP_AUTHORIZATION' in request.environ:
        try:
            auth_type, _ = request.environ['HTTP_AUTHORIZATION'].split(None, 1)
            log_entry['environment']['HTTP_AUTHORIZATION'] = f'{auth_type} ...REDACTED...'
        except:
            pass

    if user is not None:
        log_entry['user'] = user.username

    logger.info('Request: %s', log_entry)
