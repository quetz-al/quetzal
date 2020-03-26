from dataclasses import dataclass
from typing import Optional

import pytest


@dataclass(frozen=True)
class MockedTask:
    id: str
    parent: Optional['MockedTask']


@pytest.fixture(scope='function')
def mocked_signature_apply_async(mocker, request):
    """Fixture to mock celery's signature apply_async

    Use this fixture for tests that use celery but should not trigger a
    background celery job.
    """
    mocked_task = MockedTask(id=f'mocked_task_for_{request.function.__name__}',
                             parent=None)
    yield mocker.patch('celery.canvas.Signature.apply_async',
                       return_value=mocked_task)


@pytest.fixture(scope='function')
def mocked_chained_apply_async(mocker, request):
    """Fixture to mock celery's chained apply_async

    Use this fixture for tests that use celery but should not trigger a
    background celery job, but that use a chain of tasks
    """
    mocked_task = MockedTask(id=f'mocked_task_for_{request.function.__name__}',
                             parent=None)
    yield mocker.patch('celery.canvas._chain.apply_async',
                       return_value=mocked_task)
