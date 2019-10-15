import base64
import logging


logger = logging.getLogger(__name__)


def gdpr_log_request():
    from flask import request
    from quetzal.app.models import ApiKey, User

    # Quit early if the logging level is not low enough
    if logger.getEffectiveLevel() > logging.DEBUG:
        return

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
                user = User.query.filter_by(username=username).first()
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

    if 'X-Api-Key' in request.headers:
        key = request.headers['X-Api-Key']
        log_entry['headers']['X-Api-Key'] = f'...REDACTED...'
        try:
            api_key = ApiKey.check_key(key)
            if api_key is not None:
                user = api_key.user
        except:
            logger.debug('Could not determine user', exc_info=True)

    if 'HTTP_X_API_KEY' in request.environ:
        log_entry['environment']['HTTP_X_API_KEY'] = f'...REDACTED...'

    if user is not None:
        log_entry['user'] = user.username

    logger.debug('Request: %s', log_entry)
