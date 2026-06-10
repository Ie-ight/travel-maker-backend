"""place 테스트 공용 픽스처. 파일별 중복 정의 대신 여기서 한 번만 정의한다."""

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()
