import pytest
from rest_framework.test import APIClient

from apps.place.tests.factories import PlaceFactory, TagFactory

PLACE_LIST_URL = "/api/v1/places/"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestPlaceListView:
    def test_empty_list(self, api_client: APIClient) -> None:
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200

    def test_response_has_pagination_fields(self, api_client: APIClient) -> None:
        response = api_client.get(PLACE_LIST_URL)
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data

    def test_returns_place_data(self, api_client: APIClient) -> None:
        place = PlaceFactory(place_name="서울 타워", description="멋진 전망대", rating_avg="4.5")  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["count"] == 1
        result = response.data["results"][0]
        assert result["id"] == place.id
        assert result["place_name"] == "서울 타워"
        assert result["description"] == "멋진 전망대"
        assert result["bookmark_count"] == 0
        assert result["rating_avg"] == "4.5"
        assert result["image_url"] == "main.jpg"
        assert len(result["tags"]) == 2

    def test_image_url_returns_main_image(self, api_client: APIClient) -> None:
        PlaceFactory()  # type: ignore[misc]  # 기본 생성: 대표 1장 + 비대표 2장
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["image_url"] == "main.jpg"

    def test_image_url_is_null_when_no_image(self, api_client: APIClient) -> None:
        PlaceFactory(images=[])  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["image_url"] is None

    def test_tags_included_in_response(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="조용한")  # type: ignore[misc]
        PlaceFactory(tags=[tag])  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        tags = response.data["results"][0]["tags"]
        assert len(tags) == 1
        assert tags[0]["id"] == tag.id
        assert tags[0]["tag_name"] == "조용한"

    def test_rating_avg_is_null_by_default(self, api_client: APIClient) -> None:
        PlaceFactory()  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["rating_avg"] is None

    def test_default_page_size_is_8(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["count"] == 10
        assert len(response.data["results"]) == 8

    def test_custom_page_size(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(5)  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL, {"page_size": 3})
        assert len(response.data["results"]) == 3

    def test_second_page_returns_remaining_results(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL, {"page": 2, "page_size": 8})
        assert response.status_code == 200
        assert len(response.data["results"]) == 2
        assert response.data["previous"] is not None
        assert response.data["next"] is None
