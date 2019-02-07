import logging

logger = logging.getLogger(__name__)


_REQUEST_DEBUG_FMT = """Request information: [[
Path: %s
Endpoint: %s
Environ:
\t%s
Headers:
\t%s
Data:
\t%s%s%s
]]"""


_RESPONSE_DEBUG_FMT = """Response information: [[
Status: %s
Headers:
\t%s
Data:
\t%s%s
]]"""


_MAX_DATA_LENGTH_BYTES = 256


def debug_request():
    # Quit early if the logging level is not low enough
    if logger.getEffectiveLevel() > logging.DEBUG:
        return

    from flask import request
    headers_str = '\n\t'.join(f'{k!r}: {v!r}' for k, v in request.headers)
    environ_str = '\n\t'.join(f'{k!r}: {v!r}' for k, v in request.environ.items())
    truncated = ''
    data_str = request.data[:_MAX_DATA_LENGTH_BYTES]
    if len(request.data) > _MAX_DATA_LENGTH_BYTES:
        truncated = '... truncated ...'
    if request.files:
        files_str = '\n\t'.join(f'{k!r}: {v!r}' for k, v in request.files.items())
        files_str = f'\nFiles:\n\t{files_str}'
    else:
        files_str = ''
    logger.debug(_REQUEST_DEBUG_FMT, request.path, request.endpoint,
                 environ_str, headers_str, data_str, truncated, files_str)


def debug_response(response):
    # Quit early if the logging level is not low enough
    if logger.getEffectiveLevel() > logging.DEBUG:
        return response

    headers_str = '\n\t'.join(f'{k!r}: {v!r}' for k, v in response.headers)
    truncated = ''
    if response.direct_passthrough:
        data_str = 'omitted (direct_passthrough)'
    else:
        data_str = response.data[:_MAX_DATA_LENGTH_BYTES]
        if len(response.data) > _MAX_DATA_LENGTH_BYTES:
            truncated = '... truncated ...'
    logger.debug(_RESPONSE_DEBUG_FMT, response.status, headers_str, data_str, truncated)
    return response


