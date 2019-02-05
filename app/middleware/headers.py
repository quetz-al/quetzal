import logging

logger = logging.getLogger(__name__)


class HttpHostHeaderMiddleware(object):

    def __init__(self, app, server=None):
        self.app = app
        self.server = server

    def __call__(self, environ, start_response):
        logger.debug('ReverseProxied middleware')
        server = environ.get('HTTP_X_FORWARDED_SERVER', '') or self.server
        if server:
            logger.debug('Setting HTTP_HOST to %s', server)
            environ['HTTP_HOST'] = server
        tmp = self.app(environ, start_response)
        return tmp
