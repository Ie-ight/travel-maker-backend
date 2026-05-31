import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.bookmark.models import Bookmark
from apps.place.models import Place
from apps.place.tests.factories import PlaceFactory, TagFactory, UserFactory
from apps.review.models import Review

PLACE_LIST_URL = "/api/v1/places/"
PLACE_SEARCH_URL = reverse("place_search")


def _add_bookmarks(place: Place, n: int) -> None:
    for _ in range(n):
        Bookmark.objects.create(user=UserFactory(), place=place)  # type: ignore[misc]


def _add_reviews(place: Place, n: int) -> None:
    for _ in range(n):
        Review.objects.create(user=UserFactory(), place=place, rating=5, content="good")  # type: ignore[misc]


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

    def test_default_sort_by_bookmark_desc(self, api_client: APIClient) -> None:
        low = PlaceFactory()  # type: ignore[misc]
        high = PlaceFactory()  # type: ignore[misc]
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_LIST_URL)
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id]

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


@pytest.mark.django_db
class TestPlaceSearchView:
    def test_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(PLACE_SEARCH_URL)
        assert response.status_code == 200

    def test_empty_keyword_returns_all(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL)
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_blank_keyword_returns_all(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "   "})
        assert response.data["count"] == 3

    def test_keyword_partial_match(self, api_client: APIClient) -> None:
        seoul = PlaceFactory(place_name="서울 타워")  # type: ignore[misc]
        PlaceFactory(place_name="부산 타워")  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == seoul.id

    def test_keyword_does_not_match_tag_or_description(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="조용한")  # type: ignore[misc]
        PlaceFactory(place_name="한강공원", description="조용한 곳", tags=[tag])  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "조용한"})
        assert response.data["count"] == 0

    def test_response_shape_matches_list(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="서울 타워", description="멋진 곳", rating_avg="4.5")  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        result = response.data["results"][0]
        assert set(result.keys()) == {
            "id",
            "place_name",
            "image_url",
            "description",
            "bookmark_count",
            "rating_avg",
            "tags",
        }
        assert "review_count" not in result

    def test_counts_not_inflated_by_join(self, api_client: APIClient) -> None:
        place = PlaceFactory(place_name="서울")  # type: ignore[misc]
        _add_bookmarks(place, 3)
        _add_reviews(place, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        # 북마크/리뷰를 동시에 annotate 하면 distinct 없이는 3*2=6 으로 부풀려진다
        assert response.data["results"][0]["bookmark_count"] == 3

    def test_default_sort_by_bookmark_desc(self, api_client: APIClient) -> None:
        low = PlaceFactory(place_name="서울 A")  # type: ignore[misc]
        high = PlaceFactory(place_name="서울 B")  # type: ignore[misc]
        _add_bookmarks(low, 1)
        _add_bookmarks(high, 3)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id]

    def test_tie_break_by_id_desc(self, api_client: APIClient) -> None:
        # 정렬 기준이 동률(bookmark_count 0)이면 id 내림차순으로 결정적 정렬
        a = PlaceFactory(place_name="서울 A")  # type: ignore[misc]
        b = PlaceFactory(place_name="서울 B")  # type: ignore[misc]
        c = PlaceFactory(place_name="서울 C")  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert [r["id"] for r in response.data["results"]] == [c.id, b.id, a.id]

    def test_sort_by_review_desc(self, api_client: APIClient) -> None:
        a = PlaceFactory(place_name="서울 A")  # type: ignore[misc]
        b = PlaceFactory(place_name="서울 B")  # type: ignore[misc]
        _add_reviews(a, 1)
        _add_reviews(b, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "review", "order": "desc"})
        assert [r["id"] for r in response.data["results"]] == [b.id, a.id]

    def test_sort_by_rating_desc_nulls_last(self, api_client: APIClient) -> None:
        no_rating = PlaceFactory(place_name="서울 A")  # type: ignore[misc]
        low = PlaceFactory(place_name="서울 B", rating_avg="3.0")  # type: ignore[misc]
        high = PlaceFactory(place_name="서울 C", rating_avg="4.5")  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "rating", "order": "desc"})
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id, no_rating.id]

    def test_order_asc(self, api_client: APIClient) -> None:
        low = PlaceFactory(place_name="서울 A")  # type: ignore[misc]
        high = PlaceFactory(place_name="서울 B")  # type: ignore[misc]
        _add_bookmarks(low, 1)
        _add_bookmarks(high, 3)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "bookmark", "order": "asc"})
        assert [r["id"] for r in response.data["results"]] == [low.id, high.id]

    def test_invalid_sort_falls_back_to_bookmark(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="서울 A")  # type: ignore[misc]
        high = PlaceFactory(place_name="서울 B")  # type: ignore[misc]
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "invalid"})
        assert response.status_code == 200
        assert response.data["results"][0]["id"] == high.id

    def test_invalid_order_falls_back_to_desc(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="서울 A")  # type: ignore[misc]
        high = PlaceFactory(place_name="서울 B")  # type: ignore[misc]
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "order": "weird"})
        assert response.data["results"][0]["id"] == high.id

    def test_default_page_size_is_8(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL)
        assert response.data["count"] == 10
        assert len(response.data["results"]) == 8

    def test_custom_page_size(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(5)  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"page_size": 3})
        assert len(response.data["results"]) == 3
