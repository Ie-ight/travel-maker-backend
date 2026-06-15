from collections.abc import Generator

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache() -> Generator[None, None, None]:
    cache.clear()
    yield
    cache.clear()
