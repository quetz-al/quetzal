from unittest.mock import patch

from app.api.data.workspace import create


def test_create_workspace(user):
    request = {
        "name": "utws",
        "description": "Unit test workspace description",
        "families": {
            "base": None
        }
    }

    with patch('celery.canvas._chain.apply_async', autospec=True) as async_mock:
        response, code = create(body=request, user=user)
        async_mock.assert_called_once()
        # TODO: add asserts on the response object
