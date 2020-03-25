import logging
import pathlib
import urllib3
import warnings

import pytest
import requests  # Note: do not confuse with pytest request fixture
from pytest_docker.plugin import get_docker_services
from requests.exceptions import ConnectionError


logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Reference to root-level docker-compose.yaml file"""
    path = pathlib.Path(str(pytestconfig.rootdir)) / 'docker-compose.yaml'
    return str(path.resolve())


@pytest.fixture(scope="session")
def docker_compose_project_name():
    """Name for the docker-compose project when managed by pytest.

    See the url fixture for more details.
    """
    return 'quetzal-unit-tests'


@pytest.fixture(scope="session")
def docker_services(docker_compose_file, docker_compose_project_name):
    """Start all services from a docker compose file (`docker-compose up`).
    After test are finished, shutdown all services (`docker-compose down`).

    This fixture is a rewrite of the original fixture in pytest_docker, but
    uses the logger to show the progress of the docker-compose operations,
    which can be a bit slow.
    """

    logger.debug('Preparing docker-compose services')
    with get_docker_services(
        docker_compose_file, docker_compose_project_name
    ) as docker_service:
        yield docker_service
        logger.debug('Shutting down docker-compose services')


def http_is_responsive(url):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url,  allow_redirects=True, verify=False)
            return response.status_code == 200
    except ConnectionError:
        return False


def db_is_responsive(url):
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
    try:
        logger.debug('Trying to connect to DB at %s', url)
        engine = create_engine(url)
        engine.connect()
        return True
    except OperationalError:
        return False


@pytest.fixture(scope="session")
def web_service(app_config, request):
    """A responsive HTTPS service from docker-compose"""
    if app_config.TEST_USE_DOCKER_COMPOSE:
        docker_services = request.getfixturevalue('docker_services')
        docker_ip = request.getfixturevalue('docker_ip')
        url = f'https://{docker_ip}'

        logger.debug('Waiting until docker-compose HTTP service is responsive')
        docker_services.wait_until_responsive(
            timeout=30.0, pause=0.1, check=lambda: http_is_responsive(url)
        )
    else:
        url = 'https://localhost'
    return url


@pytest.fixture(scope="session")
def db_service(app_config, request):
    """A responsive DB service from docker-compose"""
    if app_config.TEST_USE_DOCKER_COMPOSE:
        docker_services = request.getfixturevalue('docker_services')
        url = app_config.SQLALCHEMY_DATABASE_URI

        logger.debug('Waiting until docker-compose BD services is responsive')
        docker_services.wait_until_responsive(
            timeout=30.0, pause=0.1, check=lambda: db_is_responsive(url)
        )
    return app_config.SQLALCHEMY_DATABASE_URI
