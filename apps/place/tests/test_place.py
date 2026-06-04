import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.bookmark.models import Bookmark
from apps.place.models import Place
from apps.place.services.place_services import get_place_detail
from apps.place.tests.factories import PlaceFactory, PlaceImageFactory, TagFactory, UserFactory
from apps.review.models import Review

PLACE_LIST_URL = "/api/v1/places/"
PLACE_SEARCH_URL = reverse("place_search")
PLACE_FILTER_URL = reverse("place_filter")


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
        assert result["rating_avg"] == 4.5
        assert result["image_url"] == "main.jpg"
        assert len(result["tags"]) == 2

    def test_inactive_place_excluded(self, api_client: APIClient) -> None:
        # 소프트삭제(is_active=False) 장소는 목록에서 제외 (단계 7)
        active = PlaceFactory(place_name="활성")  # type: ignore[misc]
        PlaceFactory(place_name="삭제됨", is_active=False)  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == active.id

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

    def test_rating_avg_is_zero_by_default(self, api_client: APIClient) -> None:
        PlaceFactory()  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["rating_avg"] == 0

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

    def test_out_of_range_page_returns_404(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL, {"page": 99, "page_size": 8})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_page_zero_returns_404(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL, {"page": 0})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_page_size_capped_at_max(self, api_client: APIClient) -> None:
        # max_page_size=100 이므로 그보다 큰 요청은 100으로 제한
        PlaceFactory.create_batch(101, images=[], tags=[])  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL, {"page_size": 500})
        assert response.data["count"] == 101
        assert len(response.data["results"]) == 100

    def test_image_url_is_null_when_no_main_image(self, api_client: APIClient) -> None:
        # 이미지는 있지만 대표(is_main)가 없으면 None
        place = PlaceFactory(images=[])  # type: ignore[misc]
        PlaceImageFactory(place=place, is_main=False, image_url="a.jpg")  # type: ignore[misc]
        PlaceImageFactory(place=place, is_main=False, image_url="b.jpg")  # type: ignore[misc]
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["image_url"] is None


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

    def test_sort_by_rating_desc(self, api_client: APIClient) -> None:
        no_rating = PlaceFactory(place_name="서울 A")  # type: ignore[misc]  # 미평가=0
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

    def test_out_of_range_page_returns_404(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"page": 99, "page_size": 8})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_sort_by_rating_asc(self, api_client: APIClient) -> None:
        no_rating = PlaceFactory(place_name="서울 A")  # type: ignore[misc]  # 미평가=0 → asc 맨 앞
        low = PlaceFactory(place_name="서울 B", rating_avg="3.0")  # type: ignore[misc]
        high = PlaceFactory(place_name="서울 C", rating_avg="4.5")  # type: ignore[misc]
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "rating", "order": "asc"})
        assert [r["id"] for r in response.data["results"]] == [no_rating.id, low.id, high.id]


@pytest.mark.django_db
class TestPlaceFilterView:
    # --- 인증 / 기본 동작 ---
    def test_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(PLACE_FILTER_URL)
        assert response.status_code == 200

    def test_no_tags_returns_all(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL)
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_no_tags_default_sort_bookmark_desc(self, api_client: APIClient) -> None:
        low = PlaceFactory()  # type: ignore[misc]
        high = PlaceFactory()  # type: ignore[misc]
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_FILTER_URL)
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id]

    # --- 태그 매칭 (AND 핵심) ---
    def test_single_tag_filters(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="산")  # type: ignore[misc]
        target = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        PlaceFactory(tags=[tag_b])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    def test_multiple_tags_require_all(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="힐링")  # type: ignore[misc]
        both = PlaceFactory(tags=[tag_a, tag_b])  # type: ignore[misc]
        PlaceFactory(tags=[tag_a])  # type: ignore[misc]  # 하나만 가진 장소는 제외돼야 함
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == both.id

    def test_and_no_match_returns_empty(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="산")  # type: ignore[misc]
        PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        PlaceFactory(tags=[tag_b])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        assert response.data["count"] == 0

    def test_tag_with_extra_tags_still_matches_no_duplicate(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="힐링")  # type: ignore[misc]
        tag_c = TagFactory(tag_name="가족")  # type: ignore[misc]
        place = PlaceFactory(tags=[tag_a, tag_b, tag_c])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        # 태그를 더 가진 장소도 매칭되며, 다중 JOIN에도 행 중복이 없어 1건이어야 함
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == place.id

    def test_nonexistent_tag_returns_empty(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": 999999})
        assert response.data["count"] == 0

    def test_duplicate_tag_ids_no_error(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        target = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_a.id]})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    # --- 파라미터 파싱 엣지케이스 ---
    def test_comma_separated_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="힐링")  # type: ignore[misc]
        both = PlaceFactory(tags=[tag_a, tag_b])  # type: ignore[misc]
        PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": f"{tag_a.id},{tag_b.id}"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == both.id

    def test_mixed_valid_invalid_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="산")  # type: ignore[misc]
        target = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        PlaceFactory(tags=[tag_b])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, "abc"]})
        # 유효한 태그만 적용
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    def test_invalid_tag_param_ignored(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(2)  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": "abc"})
        assert response.data["count"] == 2

    def test_empty_tags_param_ignored(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(2)  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": ""})
        assert response.data["count"] == 2

    def test_whitespace_tags_parsed(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="산")  # type: ignore[misc]
        target = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        PlaceFactory(tags=[tag_b])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": f" {tag_a.id} "})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    # --- keyword + tags 조합 ---
    def test_keyword_and_tags_combined(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="산")  # type: ignore[misc]
        target = PlaceFactory(place_name="서울 타워", tags=[tag_a])  # type: ignore[misc]
        PlaceFactory(place_name="부산 타워", tags=[tag_a])  # type: ignore[misc]  # 태그는 맞지만 keyword 불일치
        PlaceFactory(place_name="서울 공원", tags=[tag_b])  # type: ignore[misc]  # keyword 맞지만 태그 불일치
        response = api_client.get(PLACE_FILTER_URL, {"keyword": "서울", "tags": tag_a.id})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    def test_keyword_excludes_tag_match(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory(place_name="부산 타워", tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"keyword": "서울", "tags": tag_a.id})
        assert response.data["count"] == 0

    def test_blank_keyword_with_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        target = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"keyword": "   ", "tags": tag_a.id})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    # --- 정렬 재사용 (기존 /search와 동일 동작) ---
    def test_sort_by_rating_desc_with_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        no_rating = PlaceFactory(tags=[tag_a])  # type: ignore[misc]  # 미평가=0
        low = PlaceFactory(rating_avg="3.0", tags=[tag_a])  # type: ignore[misc]
        high = PlaceFactory(rating_avg="4.5", tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "sort": "rating", "order": "desc"})
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id, no_rating.id]

    def test_order_asc_with_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        low = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        high = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        _add_bookmarks(low, 1)
        _add_bookmarks(high, 3)
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "sort": "bookmark", "order": "asc"})
        assert [r["id"] for r in response.data["results"]] == [low.id, high.id]

    def test_invalid_sort_falls_back_to_bookmark(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        high = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "sort": "invalid"})
        assert response.status_code == 200
        assert response.data["results"][0]["id"] == high.id

    def test_tie_break_by_id_desc(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        a = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        b = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        c = PlaceFactory(tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert [r["id"] for r in response.data["results"]] == [c.id, b.id, a.id]

    # --- 카운트 정확성 ---
    def test_counts_not_inflated_by_join(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        tag_b = TagFactory(tag_name="힐링")  # type: ignore[misc]
        place = PlaceFactory(tags=[tag_a, tag_b])  # type: ignore[misc]
        _add_bookmarks(place, 3)
        _add_reviews(place, 2)
        # 다중 태그 JOIN + 북마크/리뷰 JOIN에도 distinct로 카운트가 부풀려지지 않아야 함
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        assert response.data["count"] == 1
        assert response.data["results"][0]["bookmark_count"] == 3

    # --- 응답 형태 / 페이지네이션 ---
    def test_response_shape_matches_list(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory(place_name="서울 타워", description="멋진 곳", rating_avg="4.5", tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert {"count", "next", "previous", "results"} <= set(response.data.keys())
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

    def test_default_page_size_is_8(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory.create_batch(10, tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert response.data["count"] == 10
        assert len(response.data["results"]) == 8

    def test_custom_page_size(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory.create_batch(5, tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "page_size": 3})
        assert len(response.data["results"]) == 3

    def test_out_of_range_page_returns_404(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory.create_batch(10, tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "page": 99, "page_size": 8})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_page_zero_returns_404(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")  # type: ignore[misc]
        PlaceFactory.create_batch(3, tags=[tag_a])  # type: ignore[misc]
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "page": 0})
        assert response.status_code == 404
        assert "error_detail" in response.data


@pytest.mark.django_db
class TestPlaceDetailView:
    def _url(self, place_id: int) -> str:
        return reverse("place_detail", args=[place_id])

    def test_no_auth_required(self, api_client: APIClient) -> None:
        place = PlaceFactory()  # type: ignore[misc]
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200

    def test_returns_detail_fields(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="바다")  # type: ignore[misc]
        place = PlaceFactory(  # type: ignore[misc]
            place_name="협재해변",
            description="상세설명",
            rating_avg="4.5",
            tags=[tag],
        )
        _add_bookmarks(place, 3)
        response = api_client.get(self._url(place.id))
        data = response.data
        assert response.status_code == 200
        assert data["id"] == place.id
        assert data["place_name"] == "협재해변"
        assert data["description"] == "상세설명"
        assert data["rating_avg"] == 4.5
        assert data["review_count"] == 0
        assert data["bookmark_count"] == 3
        assert data["tags"][0]["tag_name"] == "바다"
        assert isinstance(data["images"], list)
        assert set(data.keys()) == {
            "id",
            "place_name",
            "description",
            "latitude",
            "longitude",
            "rating_avg",
            "review_count",
            "bookmark_count",
            "images",
            "tags",
        }

    def test_lat_lng_rating_avg_are_numbers(self, api_client: APIClient) -> None:
        place = PlaceFactory(rating_avg="4.5")  # type: ignore[misc]
        data = api_client.get(self._url(place.id)).data
        assert isinstance(data["latitude"], float)
        assert isinstance(data["longitude"], float)
        assert isinstance(data["rating_avg"], float)

    def test_rating_avg_is_zero_when_no_review(self, api_client: APIClient) -> None:
        place = PlaceFactory()  # type: ignore[misc]  # rating_avg 기본 0
        data = api_client.get(self._url(place.id)).data
        assert data["rating_avg"] == 0

    def test_tags_use_tag_name_key(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="힐링")  # type: ignore[misc]
        place = PlaceFactory(tags=[tag])  # type: ignore[misc]
        data = api_client.get(self._url(place.id)).data
        assert set(data["tags"][0].keys()) == {"id", "tag_name"}
        assert data["tags"][0]["tag_name"] == "힐링"

    def test_images_main_first_then_order(self, api_client: APIClient) -> None:
        place = PlaceFactory(images=[])  # type: ignore[misc]
        PlaceImageFactory(place=place, is_main=False, order=1, image_url="sub.jpg")  # type: ignore[misc]
        PlaceImageFactory(place=place, is_main=True, order=5, image_url="main.jpg")  # type: ignore[misc]
        data = api_client.get(self._url(place.id)).data
        assert data["images"] == ["main.jpg", "sub.jpg"]

    def test_bookmark_count(self, api_client: APIClient) -> None:
        place = PlaceFactory()  # type: ignore[misc]
        _add_bookmarks(place, 4)
        data = api_client.get(self._url(place.id)).data
        assert data["bookmark_count"] == 4

    def test_404_when_not_found(self, api_client: APIClient) -> None:
        response = api_client.get(self._url(999999))
        assert response.status_code == 404
        assert response.data["error_detail"] == "존재하지 않는 장소입니다."

    def test_images_empty_when_no_image(self, api_client: APIClient) -> None:
        place = PlaceFactory(images=[])  # type: ignore[misc]
        data = api_client.get(self._url(place.id)).data
        assert data["images"] == []

    def test_tags_empty_when_no_tags(self, api_client: APIClient) -> None:
        place = PlaceFactory(tags=[])  # type: ignore[misc]
        data = api_client.get(self._url(place.id)).data
        assert data["tags"] == []

    def test_lat_lng_values_round_trip(self, api_client: APIClient) -> None:
        # Decimal -> float 직렬화 시 좌표 값이 그대로 보존되는지 (정밀도 손실 없음)
        place = PlaceFactory(latitude="37.5540000", longitude="126.2390000")  # type: ignore[misc]
        data = api_client.get(self._url(place.id)).data
        assert data["latitude"] == pytest.approx(37.554)
        assert data["longitude"] == pytest.approx(126.239)

    def test_returns_requested_place_among_many(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="다른 장소")  # type: ignore[misc]
        target = PlaceFactory(place_name="목표 장소")  # type: ignore[misc]
        data = api_client.get(self._url(target.id)).data
        assert data["id"] == target.id
        assert data["place_name"] == "목표 장소"

    def test_review_count(self, api_client: APIClient) -> None:
        place = PlaceFactory()  # type: ignore[misc]
        _add_reviews(place, 2)
        data = api_client.get(self._url(place.id)).data
        assert data["review_count"] == 2

    def test_counts_not_inflated_by_join(self, api_client: APIClient) -> None:
        # bookmark/review 동시 annotate 시 distinct 없으면 3*2=6 으로 부풀려진다
        place = PlaceFactory()  # type: ignore[misc]
        _add_bookmarks(place, 3)
        _add_reviews(place, 2)
        data = api_client.get(self._url(place.id)).data
        assert data["bookmark_count"] == 3
        assert data["review_count"] == 2

    def test_service_returns_none_when_not_found(self) -> None:
        # 서비스는 DRF 없이 순수하게 None을 반환한다 (404 판단은 뷰가 함)
        assert get_place_detail(999999) is None

    def test_inactive_place_returns_404(self, api_client: APIClient) -> None:
        # 소프트삭제 장소는 상세도 404 (단계 7)
        place = PlaceFactory(is_active=False)  # type: ignore[misc]
        response = api_client.get(self._url(place.id))
        assert response.status_code == 404

    def test_service_returns_none_when_inactive(self) -> None:
        place = PlaceFactory(is_active=False)  # type: ignore[misc]
        assert get_place_detail(place.id) is None
