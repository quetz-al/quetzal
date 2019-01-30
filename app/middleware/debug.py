import logging

logger = logging.getLogger(__name__)


_REQUEST_DEBUG_FMT = """[[Request information: [[
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


def debug_request():
    if logger.getEffectiveLevel() > logging.DEBUG:
        return

    from flask import request
    headers_str = '\n\t'.join(f'{k!r}: {v!r}' for k, v in request.headers)
    data_str = request.data[:128]
    if len(request.data) > 128:
        truncated = '... truncated ...'
    else:
        truncated = ''
    if request.files:
        files_str = '\n\t'.join(f'{k!r}: {v!r}' for k, v in request.files.items())
        files_str = f'\nFiles:\n\t{files_str}'
    else:
        files_str = ''
    logger.debug(_REQUEST_DEBUG_FMT, headers_str, data_str, truncated, files_str)


def debug_response(response):
    if logger.getEffectiveLevel() > logging.DEBUG:
        return response

    headers_str = '\n\t'.join(f'{k!r}: {v!r}' for k, v in response.headers)
    data_str = response.data[:128]
    if len(response.data) > 128:
        truncated = '... truncated ...'
    else:
        truncated = ''
    logger.debug(_RESPONSE_DEBUG_FMT, response.status, headers_str, data_str, truncated)
    return response
