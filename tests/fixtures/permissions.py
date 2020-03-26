import pytest


@pytest.fixture(scope='function')
def mocked_permissions(mocker):
    """Fixture to mock flask_principal permission verification

    Use this fixture for tests that want to bypass the permission verification
    """
    yield mocker.patch('flask_principal.Permission.can', return_value=True)
