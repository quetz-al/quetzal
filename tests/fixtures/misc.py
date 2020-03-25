import random
import string

import pytest


@pytest.fixture(scope='function')
def make_random_str():
    """Factory fixture to create random strings"""

    def factory(size: int = 8):
        size = max(1, size)
        chars = random.choices(string.ascii_letters, k=size)
        return ''.join(chars)

    return factory
