"""Hacks needed to circumvent connexion validation

There is a bug on the connexion library concerning content negotiation and
response validation. See https://github.com/zalando/connexion/issues/860

Until this issue is fixed, we need to find a way to avoid a false validation
error when a requests sends an 'application/octet-stream' accept header when
downloading files
"""
import functools
import logging

from connexion.decorators.response import ResponseValidator
from connexion import problem
from connexion.exceptions import NonConformingResponseBody, NonConformingResponseHeaders
from connexion.utils import has_coroutine

logger = logging.getLogger(__name__)


class CustomResponseValidator(ResponseValidator):

    def validate_response_with_request(self, request, data, status_code, headers, url):
        details_op = self.operation.operation_id in ('app.api.data.file.details',
                                                     'app.api.data.file.details_w')
        accept_octet_header = (request.headers.get('accept', '') == 'application/octet-stream')
        logger.info('needs circumvent? %s %s', details_op, accept_octet_header)
        if details_op and accept_octet_header:
            logging.debug('Circumventing validation for octet-stream')
            return True
        return self.validate_response(data, status_code, headers, url)

    def __call__(self, function):

        def _wrapper(request, response):
            try:
                connexion_response = \
                    self.operation.api.get_connexion_response(response, self.mimetype)
                self.validate_response_with_request(
                    request,
                    connexion_response.body, connexion_response.status_code,
                    connexion_response.headers, request.url)

            except (NonConformingResponseBody, NonConformingResponseHeaders) as e:
                response = problem(500, e.reason, e.message)
                return self.operation.api.get_response(response)

            return response

        if has_coroutine(function):  # pragma: 2.7 no cover
            from connexion.decorators.coroutine_wrappers import get_response_validator_wrapper
            wrapper = get_response_validator_wrapper(function, _wrapper)

        else:  # pragma: 3 no cover
            @functools.wraps(function)
            def wrapper(request):
                response = function(request)
                return _wrapper(request, response)

        return wrapper
