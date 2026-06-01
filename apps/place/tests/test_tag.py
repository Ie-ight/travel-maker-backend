# apps/place/tests/test_tag.py

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.place.models import Tag


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def tags() -> list[Tag]:
    Tag.objects.create(tag_type="분위기", tag_name="힐링")  # type: ignore[attr-defined]
    Tag.objects.create(tag_type="분위기", tag_name="액티비티")  # type: ignore[attr-defined]
    Tag.objects.create(tag_type="계절", tag_name="봄")  # type: ignore[attr-defined]
    return list(Tag.objects.all())  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestTagList:
    def test_태그_목록_조회_성공(self, client: APIClient, tags: list[Tag]) -> None:
        response = client.get("/api/v1/tags/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    def test_태그_타입_필터_성공(self, client: APIClient, tags: list[Tag]) -> None:
        response = client.get("/api/v1/tags/", {"tag_type": "분위기"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_존재하지_않는_태그_타입_필터(self, client: APIClient, tags: list[Tag]) -> None:
        response = client.get("/api/v1/tags/", {"tag_type": "없는타입"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0
