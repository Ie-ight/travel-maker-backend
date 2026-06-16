"""Place 목록·검색·필터·상세 뷰 API 테스트.

페이지네이션·정렬·태그 AND 매칭·응답 형태·소프트삭제 제외를 검증한다. 공용 api_client 픽스처는 conftest.py.
"""

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.bookmark.models import Bookmark
from apps.place.models import Place, PlaceFeature, PlaceInfo
from apps.place.services.place_services import get_place_detail
from apps.place.tests.factories import PlaceFactory, PlaceImageFactory, TagFactory, UserFactory
from apps.review.models import Review
from apps.travel_quiz.tests.factories import TravelTypeFactory, UserTestResultFactory

PLACE_LIST_URL = reverse("place_list")
PLACE_SEARCH_URL = reverse("place_search")
PLACE_FILTER_URL = reverse("place_filter")


def _add_bookmarks(place: Place, n: int) -> None:
    for _ in range(n):
        Bookmark.objects.create(user=UserFactory(), place=place)


def _add_reviews(place: Place, n: int) -> None:
    for _ in range(n):
        Review.objects.create(user=UserFactory(), place=place, rating=5, content="good")
    # create_review 서비스를 우회하므로 비정규화 rating_count(=review_count 표시·정렬 소스)를 직접 갱신
    place.rating_count = place.reviews.count()
    place.save(update_fields=["rating_count"])


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
        assert response.status_code == 200
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data

    def test_returns_place_data(self, api_client: APIClient) -> None:
        place = PlaceFactory(place_name="서울 타워", description="멋진 전망대", rating_avg="4.5")
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["count"] == 1
        result = response.data["results"][0]
        assert result["id"] == place.id
        assert result["place_name"] == "서울 타워"
        assert result["description"] == "멋진 전망대"
        assert result["bookmark_count"] == 0
        assert result["is_bookmarked"] is False
        assert result["rating_avg"] == 4.5
        assert result["image_url"] == "main.jpg"
        assert len(result["tags"]) == 2

    def test_is_bookmarked_true_for_authenticated_user(self, api_client: APIClient) -> None:
        user = UserFactory()
        place = PlaceFactory()
        Bookmark.objects.create(user=user, place=place)
        api_client.force_authenticate(user=user)
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["is_bookmarked"] is True

    def test_is_bookmarked_false_for_other_user(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        Bookmark.objects.create(user=UserFactory(), place=place)
        api_client.force_authenticate(user=UserFactory())
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["is_bookmarked"] is False

    def test_is_bookmarked_false_for_anonymous(self, api_client: APIClient) -> None:
        PlaceFactory()
        response = api_client.get(PLACE_LIST_URL)
        assert response.data["results"][0]["is_bookmarked"] is False

    def test_inactive_place_excluded(self, api_client: APIClient) -> None:
        # 소프트삭제(is_active=False) 장소는 목록에서 제외 (단계 7)
        active = PlaceFactory(place_name="활성")
        PlaceFactory(place_name="삭제됨", is_active=False)
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == active.id

    def test_image_url_returns_main_image(self, api_client: APIClient) -> None:
        PlaceFactory()  # 기본 생성: 대표 1장 + 비대표 2장
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["results"][0]["image_url"] == "main.jpg"

    def test_image_url_is_null_when_no_image(self, api_client: APIClient) -> None:
        PlaceFactory(images=[])
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["results"][0]["image_url"] is None

    def test_tags_included_in_response(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="조용한")
        PlaceFactory(tags=[tag])
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        tags = response.data["results"][0]["tags"]
        assert len(tags) == 1
        assert tags[0]["id"] == tag.id
        assert tags[0]["tag_name"] == "조용한"

    def test_rating_avg_is_zero_by_default(self, api_client: APIClient) -> None:
        PlaceFactory()
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["results"][0]["rating_avg"] == 0

    def test_default_sort_by_bookmark_desc(self, api_client: APIClient) -> None:
        low = PlaceFactory()
        high = PlaceFactory()
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id]

    def test_default_page_size_is_8(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["count"] == 10
        assert len(response.data["results"]) == 8

    def test_custom_page_size(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(5)
        response = api_client.get(PLACE_LIST_URL, {"page_size": 3})
        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    def test_second_page_returns_remaining_results(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)
        response = api_client.get(PLACE_LIST_URL, {"page": 2, "page_size": 8})
        assert response.status_code == 200
        assert len(response.data["results"]) == 2
        assert response.data["previous"] is not None
        assert response.data["next"] is None

    def test_out_of_range_page_returns_404(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)
        response = api_client.get(PLACE_LIST_URL, {"page": 99, "page_size": 8})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_page_zero_returns_404(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)
        response = api_client.get(PLACE_LIST_URL, {"page": 0})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_page_size_capped_at_max(self, api_client: APIClient) -> None:
        # max_page_size=100 이므로 그보다 큰 요청은 100으로 제한
        PlaceFactory.create_batch(101, images=[], tags=[])
        response = api_client.get(PLACE_LIST_URL, {"page_size": 500})
        assert response.status_code == 200
        assert response.data["count"] == 101
        assert len(response.data["results"]) == 100

    def test_image_url_is_null_when_no_main_image(self, api_client: APIClient) -> None:
        # 이미지는 있지만 대표(is_main)가 없으면 None
        place = PlaceFactory(images=[])
        PlaceImageFactory(place=place, is_main=False, image_url="a.jpg")
        PlaceImageFactory(place=place, is_main=False, image_url="b.jpg")
        response = api_client.get(PLACE_LIST_URL)
        assert response.status_code == 200
        assert response.data["results"][0]["image_url"] is None


@pytest.mark.django_db
class TestPlaceSearchView:
    def test_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(PLACE_SEARCH_URL)
        assert response.status_code == 200

    def test_empty_keyword_returns_all(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)
        response = api_client.get(PLACE_SEARCH_URL)
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_blank_keyword_returns_all(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "   "})
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_keyword_partial_match(self, api_client: APIClient) -> None:
        seoul = PlaceFactory(place_name="서울 타워")
        PlaceFactory(place_name="부산 타워")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == seoul.id

    def test_keyword_matches_tag_name(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="조용한")
        place = PlaceFactory(place_name="한강공원", tags=[tag])
        PlaceFactory(place_name="북적이는 시장", tags=[])
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "조용한"})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == place.id

    def test_keyword_matches_address(self, api_client: APIClient) -> None:
        place = PlaceFactory(place_name="어딘가", address_primary="서울특별시 강남구 테헤란로 1")
        PlaceFactory(place_name="다른곳", address_primary="부산광역시 해운대구 1")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "강남"})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == place.id

    def test_keyword_does_not_match_description(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="한강공원", description="조용한 곳", tags=[])
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "조용한"})
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_keyword_or_match_place_name_and_tag(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="바다")
        by_name = PlaceFactory(place_name="바다뷰 카페", tags=[])
        by_tag = PlaceFactory(place_name="힐링 스팟", tags=[tag])
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "바다"})
        assert response.status_code == 200
        assert response.data["count"] == 2
        ids = {r["id"] for r in response.data["results"]}
        assert ids == {by_name.id, by_tag.id}

    def test_trgm_fallback_on_no_exact_match(self, api_client: APIClient) -> None:
        # 정확 매칭 결과 없을 때 trgm 유사도 폴백으로 유사 장소 반환
        place = PlaceFactory(place_name="광안리 해수욕장")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "광안리해수욕"})
        assert response.status_code == 200
        assert response.data["count"] >= 1
        assert response.data["results"][0]["id"] == place.id

    def test_trgm_fallback_returns_empty_when_no_similar(self, api_client: APIClient) -> None:
        # 유사한 장소도 없으면 빈 결과 반환 (에러 없이)
        PlaceFactory(place_name="제주 오름")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "xyzqwerty"})
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_exact_match_prevents_trgm_fallback(self, api_client: APIClient) -> None:
        # 정확 매칭 결과가 있으면 trgm 폴백 진입 안 함
        exact = PlaceFactory(place_name="해수욕장")
        similar = PlaceFactory(place_name="해수욕장 근처 카페")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "해수욕장"})
        assert response.status_code == 200
        ids = {r["id"] for r in response.data["results"]}
        assert exact.id in ids
        assert similar.id in ids  # 둘 다 exact 매칭

    def test_response_shape_matches_list(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="서울 타워", description="멋진 곳", rating_avg="4.5")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert response.status_code == 200
        result = response.data["results"][0]
        assert set(result.keys()) == {
            "id",
            "place_name",
            "image_url",
            "description",
            "latitude",
            "longitude",
            "bookmark_count",
            "review_count",
            "is_bookmarked",
            "rating_avg",
            "tags",
        }

    def test_counts_not_inflated_by_join(self, api_client: APIClient) -> None:
        place = PlaceFactory(place_name="서울")
        _add_bookmarks(place, 3)
        _add_reviews(place, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert response.status_code == 200
        # 북마크/리뷰를 동시에 annotate 하면 distinct 없이는 3*2=6 으로 부풀려진다
        assert response.data["results"][0]["bookmark_count"] == 3

    def test_default_sort_by_bookmark_desc(self, api_client: APIClient) -> None:
        low = PlaceFactory(place_name="서울 A")
        high = PlaceFactory(place_name="서울 B")
        _add_bookmarks(low, 1)
        _add_bookmarks(high, 3)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id]

    def test_tie_break_by_id_desc(self, api_client: APIClient) -> None:
        # 정렬 기준이 동률(bookmark_count 0)이면 id 내림차순으로 결정적 정렬
        a = PlaceFactory(place_name="서울 A")
        b = PlaceFactory(place_name="서울 B")
        c = PlaceFactory(place_name="서울 C")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [c.id, b.id, a.id]

    def test_sort_by_review_desc(self, api_client: APIClient) -> None:
        a = PlaceFactory(place_name="서울 A")
        b = PlaceFactory(place_name="서울 B")
        _add_reviews(a, 1)
        _add_reviews(b, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "review", "order": "desc"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [b.id, a.id]

    def test_sort_by_rating_desc(self, api_client: APIClient) -> None:
        no_rating = PlaceFactory(place_name="서울 A")  # 미평가=0
        low = PlaceFactory(place_name="서울 B", rating_avg="3.0")
        high = PlaceFactory(place_name="서울 C", rating_avg="4.5")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "rating", "order": "desc"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id, no_rating.id]

    def test_order_asc(self, api_client: APIClient) -> None:
        low = PlaceFactory(place_name="서울 A")
        high = PlaceFactory(place_name="서울 B")
        _add_bookmarks(low, 1)
        _add_bookmarks(high, 3)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "bookmark", "order": "asc"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [low.id, high.id]

    def test_invalid_sort_falls_back_to_bookmark(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="서울 A")
        high = PlaceFactory(place_name="서울 B")
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "invalid"})
        assert response.status_code == 200
        assert response.data["results"][0]["id"] == high.id

    def test_invalid_order_falls_back_to_desc(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="서울 A")
        high = PlaceFactory(place_name="서울 B")
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "order": "weird"})
        assert response.status_code == 200
        assert response.data["results"][0]["id"] == high.id

    def test_default_page_size_is_8(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)
        response = api_client.get(PLACE_SEARCH_URL)
        assert response.status_code == 200
        assert response.data["count"] == 10
        assert len(response.data["results"]) == 8

    def test_custom_page_size(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(5)
        response = api_client.get(PLACE_SEARCH_URL, {"page_size": 3})
        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    def test_out_of_range_page_returns_404(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(10)
        response = api_client.get(PLACE_SEARCH_URL, {"page": 99, "page_size": 8})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_sort_by_rating_asc(self, api_client: APIClient) -> None:
        no_rating = PlaceFactory(place_name="서울 A")  # 미평가=0 → asc 맨 앞
        low = PlaceFactory(place_name="서울 B", rating_avg="3.0")
        high = PlaceFactory(place_name="서울 C", rating_avg="4.5")
        response = api_client.get(PLACE_SEARCH_URL, {"keyword": "서울", "sort": "rating", "order": "asc"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [no_rating.id, low.id, high.id]


@pytest.mark.django_db
class TestPlaceFilterView:
    # --- 인증 / 기본 동작 ---
    def test_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(PLACE_FILTER_URL)
        assert response.status_code == 200

    def test_no_tags_returns_all(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(3)
        response = api_client.get(PLACE_FILTER_URL)
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_no_tags_default_sort_bookmark_desc(self, api_client: APIClient) -> None:
        low = PlaceFactory()
        high = PlaceFactory()
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_FILTER_URL)
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id]

    # --- 태그 매칭 (AND 핵심) ---
    def test_single_tag_filters(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="산")
        target = PlaceFactory(tags=[tag_a])
        PlaceFactory(tags=[tag_b])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    def test_multiple_tags_require_all(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="힐링")
        both = PlaceFactory(tags=[tag_a, tag_b])
        PlaceFactory(tags=[tag_a])  # 하나만 가진 장소는 제외돼야 함
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == both.id

    def test_and_no_match_returns_empty(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="산")
        PlaceFactory(tags=[tag_a])
        PlaceFactory(tags=[tag_b])
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_tag_with_extra_tags_still_matches_no_duplicate(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="힐링")
        tag_c = TagFactory(tag_name="가족")
        place = PlaceFactory(tags=[tag_a, tag_b, tag_c])
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        assert response.status_code == 200
        # 태그를 더 가진 장소도 매칭되며, 다중 JOIN에도 행 중복이 없어 1건이어야 함
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == place.id

    def test_nonexistent_tag_returns_empty(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory(tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": 999999})
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_duplicate_tag_ids_no_error(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        target = PlaceFactory(tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_a.id]})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    # --- 파라미터 파싱 엣지케이스 ---
    def test_comma_separated_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="힐링")
        both = PlaceFactory(tags=[tag_a, tag_b])
        PlaceFactory(tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": f"{tag_a.id},{tag_b.id}"})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == both.id

    def test_mixed_valid_invalid_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="산")
        target = PlaceFactory(tags=[tag_a])
        PlaceFactory(tags=[tag_b])
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, "abc"]})
        assert response.status_code == 200
        # 유효한 태그만 적용
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    def test_invalid_tag_param_ignored(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(2)
        response = api_client.get(PLACE_FILTER_URL, {"tags": "abc"})
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_empty_tags_param_ignored(self, api_client: APIClient) -> None:
        PlaceFactory.create_batch(2)
        response = api_client.get(PLACE_FILTER_URL, {"tags": ""})
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_whitespace_tags_parsed(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="산")
        target = PlaceFactory(tags=[tag_a])
        PlaceFactory(tags=[tag_b])
        response = api_client.get(PLACE_FILTER_URL, {"tags": f" {tag_a.id} "})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    # --- keyword + tags 조합 ---
    def test_keyword_and_tags_combined(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="산")
        target = PlaceFactory(place_name="서울 타워", tags=[tag_a])
        PlaceFactory(place_name="부산 타워", tags=[tag_a])  # 태그는 맞지만 keyword 불일치
        PlaceFactory(place_name="서울 공원", tags=[tag_b])  # keyword 맞지만 태그 불일치
        response = api_client.get(PLACE_FILTER_URL, {"keyword": "서울", "tags": tag_a.id})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    def test_keyword_excludes_tag_match(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory(place_name="부산 타워", tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"keyword": "서울", "tags": tag_a.id})
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_blank_keyword_with_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        target = PlaceFactory(tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"keyword": "   ", "tags": tag_a.id})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == target.id

    # --- 정렬 재사용 (기존 /search와 동일 동작) ---
    def test_sort_by_rating_desc_with_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        no_rating = PlaceFactory(tags=[tag_a])  # 미평가=0
        low = PlaceFactory(rating_avg="3.0", tags=[tag_a])
        high = PlaceFactory(rating_avg="4.5", tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "sort": "rating", "order": "desc"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [high.id, low.id, no_rating.id]

    def test_order_asc_with_tags(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        low = PlaceFactory(tags=[tag_a])
        high = PlaceFactory(tags=[tag_a])
        _add_bookmarks(low, 1)
        _add_bookmarks(high, 3)
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "sort": "bookmark", "order": "asc"})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [low.id, high.id]

    def test_invalid_sort_falls_back_to_bookmark(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory(tags=[tag_a])
        high = PlaceFactory(tags=[tag_a])
        _add_bookmarks(high, 2)
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "sort": "invalid"})
        assert response.status_code == 200
        assert response.data["results"][0]["id"] == high.id

    def test_tie_break_by_id_desc(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        a = PlaceFactory(tags=[tag_a])
        b = PlaceFactory(tags=[tag_a])
        c = PlaceFactory(tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert response.status_code == 200
        assert [r["id"] for r in response.data["results"]] == [c.id, b.id, a.id]

    # --- 카운트 정확성 ---
    def test_counts_not_inflated_by_join(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        tag_b = TagFactory(tag_name="힐링")
        place = PlaceFactory(tags=[tag_a, tag_b])
        _add_bookmarks(place, 3)
        _add_reviews(place, 2)
        # 다중 태그 JOIN + 북마크/리뷰 JOIN에도 distinct로 카운트가 부풀려지지 않아야 함
        response = api_client.get(PLACE_FILTER_URL, {"tags": [tag_a.id, tag_b.id]})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["bookmark_count"] == 3

    # --- 응답 형태 / 페이지네이션 ---
    def test_response_shape_matches_list(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory(place_name="서울 타워", description="멋진 곳", rating_avg="4.5", tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert response.status_code == 200
        assert {"count", "next", "previous", "results"} <= set(response.data.keys())
        result = response.data["results"][0]
        assert set(result.keys()) == {
            "id",
            "place_name",
            "image_url",
            "description",
            "latitude",
            "longitude",
            "bookmark_count",
            "review_count",
            "is_bookmarked",
            "rating_avg",
            "tags",
        }

    def test_default_page_size_is_8(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory.create_batch(10, tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id})
        assert response.status_code == 200
        assert response.data["count"] == 10
        assert len(response.data["results"]) == 8

    def test_custom_page_size(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory.create_batch(5, tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "page_size": 3})
        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    def test_out_of_range_page_returns_404(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory.create_batch(10, tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "page": 99, "page_size": 8})
        assert response.status_code == 404
        assert "error_detail" in response.data

    def test_page_zero_returns_404(self, api_client: APIClient) -> None:
        tag_a = TagFactory(tag_name="바다")
        PlaceFactory.create_batch(3, tags=[tag_a])
        response = api_client.get(PLACE_FILTER_URL, {"tags": tag_a.id, "page": 0})
        assert response.status_code == 404
        assert "error_detail" in response.data


@pytest.mark.django_db
class TestPlaceDetailView:
    def _url(self, place_id: int) -> str:
        return reverse("place_detail", args=[place_id])

    def test_no_auth_required(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200

    def test_returns_detail_fields(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="바다")
        place = PlaceFactory(
            place_name="협재해변",
            description="상세설명",
            rating_avg="4.5",
            tags=[tag],
        )
        response = api_client.get(self._url(place.id))
        data = response.data
        assert response.status_code == 200
        assert data["id"] == place.id
        assert data["place_name"] == "협재해변"
        assert data["description"] == "상세설명"
        assert data["rating_avg"] == 4.5
        assert data["review_count"] == 0
        assert data["tags"][0]["tag_name"] == "바다"
        assert isinstance(data["images"], list)
        assert data["is_bookmarked"] is False
        assert set(data.keys()) == {
            "id",
            "place_name",
            "description",
            "latitude",
            "longitude",
            "homepage",
            "tel",
            "address_primary",
            "address_detail",
            "rating_avg",
            "review_count",
            "is_bookmarked",
            "images",
            "tags",
            "info",
        }

    def test_info_includes_place_info(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        PlaceInfo.objects.create(
            place=place, parking=True, pet=False, admission_fee="무료", operating_hours="09:00~18:00"
        )
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        info = response.data["info"]
        assert info["parking"] is True  # boolean 그대로
        assert info["pet"] is False
        assert info["admission_fee"] == "무료"
        assert info["operating_hours"] == "09:00~18:00"
        assert set(info.keys()) == {
            "operating_hours",
            "closed_days",
            "parking",
            "admission_fee",
            "spend_time",
            "discount_info",
            "accom_count",
            "pet",
            "baby_carriage",
            "credit_card",
        }

    def test_info_null_when_no_place_info(self, api_client: APIClient) -> None:
        place = PlaceFactory()  # PlaceInfo 없는 장소(14%)
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        assert response.data["info"] is None

    def test_lat_lng_rating_avg_are_numbers(self, api_client: APIClient) -> None:
        place = PlaceFactory(rating_avg="4.5")
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        data = response.data
        assert isinstance(data["latitude"], float)
        assert isinstance(data["longitude"], float)
        assert isinstance(data["rating_avg"], float)

    def test_rating_avg_is_zero_when_no_review(self, api_client: APIClient) -> None:
        place = PlaceFactory()  # rating_avg 기본 0
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        assert response.data["rating_avg"] == 0

    def test_tags_use_tag_name_key(self, api_client: APIClient) -> None:
        tag = TagFactory(tag_name="힐링")
        place = PlaceFactory(tags=[tag])
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        data = response.data
        assert set(data["tags"][0].keys()) == {"id", "tag_name"}
        assert data["tags"][0]["tag_name"] == "힐링"

    def test_images_main_first_then_order(self, api_client: APIClient) -> None:
        place = PlaceFactory(images=[])
        PlaceImageFactory(place=place, is_main=False, order=1, image_url="sub.jpg")
        PlaceImageFactory(place=place, is_main=True, order=5, image_url="main.jpg")
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        assert response.data["images"] == ["main.jpg", "sub.jpg"]

    def test_404_when_not_found(self, api_client: APIClient) -> None:
        response = api_client.get(self._url(999999))
        assert response.status_code == 404
        assert response.data["error_detail"] == "존재하지 않는 장소입니다."

    def test_view_count_increments_on_each_request(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        assert place.view_count == 0

        api_client.get(self._url(place.id))
        place.refresh_from_db()
        assert place.view_count == 1

        api_client.get(self._url(place.id))
        place.refresh_from_db()
        assert place.view_count == 2

    def test_view_count_not_incremented_on_404(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        api_client.get(self._url(999999))
        place.refresh_from_db()
        assert place.view_count == 0

    def test_view_count_not_incremented_for_inactive_place(self, api_client: APIClient) -> None:
        place = PlaceFactory(is_active=False)
        response = api_client.get(self._url(place.id))
        assert response.status_code == 404
        place.refresh_from_db()
        assert place.view_count == 0

    def test_images_empty_when_no_image(self, api_client: APIClient) -> None:
        place = PlaceFactory(images=[])
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        assert response.data["images"] == []

    def test_tags_empty_when_no_tags(self, api_client: APIClient) -> None:
        place = PlaceFactory(tags=[])
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        assert response.data["tags"] == []

    def test_lat_lng_values_round_trip(self, api_client: APIClient) -> None:
        # Decimal -> float 직렬화 시 좌표 값이 그대로 보존되는지 (정밀도 손실 없음)
        place = PlaceFactory(latitude="37.5540000", longitude="126.2390000")
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        data = response.data
        assert data["latitude"] == pytest.approx(37.554)
        assert data["longitude"] == pytest.approx(126.239)

    def test_returns_requested_place_among_many(self, api_client: APIClient) -> None:
        PlaceFactory(place_name="다른 장소")
        target = PlaceFactory(place_name="목표 장소")
        response = api_client.get(self._url(target.id))
        assert response.status_code == 200
        data = response.data
        assert data["id"] == target.id
        assert data["place_name"] == "목표 장소"

    def test_review_count(self, api_client: APIClient) -> None:
        place = PlaceFactory()
        _add_reviews(place, 2)
        response = api_client.get(self._url(place.id))
        assert response.status_code == 200
        assert response.data["review_count"] == 2

    def test_service_returns_none_when_not_found(self) -> None:
        # 서비스는 DRF 없이 순수하게 None을 반환한다 (404 판단은 뷰가 함)
        assert get_place_detail(999999) is None

    def test_inactive_place_returns_404(self, api_client: APIClient) -> None:
        # 소프트삭제 장소는 상세도 404 (단계 7)
        place = PlaceFactory(is_active=False)
        response = api_client.get(self._url(place.id))
        assert response.status_code == 404

    def test_service_returns_none_when_inactive(self) -> None:
        place = PlaceFactory(is_active=False)
        assert get_place_detail(place.id) is None


PLACE_RECOMMEND_URL = PLACE_SEARCH_URL  # sort=recommend 파라미터로 동일 엔드포인트 호출


@pytest.mark.django_db
class TestPlaceRecommendHybridSearch:
    """sort=recommend + keyword 하이브리드 검색 (Phase 3) 테스트."""

    def setup_method(self) -> None:
        cache.clear()

    def _make_user_with_vector(self, vector: list[float]):
        travel_type = TravelTypeFactory()
        return UserTestResultFactory(travel_type=travel_type, result_vector=vector).user

    def test_hybrid_returns_keyword_matching_places(self, api_client: APIClient) -> None:
        # 벡터 보유 유저 + keyword → 키워드 매칭 장소만 반환
        user = self._make_user_with_vector([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        match = PlaceFactory(place_name="해운대 해수욕장")
        non_match = PlaceFactory(place_name="경복궁")  # keyword 미매칭
        api_client.force_authenticate(user=user)
        response = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "해운대", "sort": "recommend"})
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert match.id in ids
        assert non_match.id not in ids

    def test_hybrid_orders_by_combined_score(self, api_client: APIClient) -> None:
        # vec_score 높은 장소가 상위에 오는지 확인
        user = self._make_user_with_vector([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        high_vec = PlaceFactory(place_name="부산 해수욕장")
        low_vec = PlaceFactory(place_name="서울 해수욕장")
        # high_vec: 유저 벡터와 거의 동일 (유사도 높음)
        PlaceFeature.objects.create(place=high_vec, style_vector=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        # low_vec: 유저 벡터와 반대 (유사도 낮음)
        PlaceFeature.objects.create(place=low_vec, style_vector=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0])
        api_client.force_authenticate(user=user)
        response = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "해수욕장", "sort": "recommend"})
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert ids.index(high_vec.id) < ids.index(low_vec.id)

    def test_hybrid_empty_on_no_match(self, api_client: APIClient) -> None:
        # keyword 매칭 없으면 빈 결과
        user = self._make_user_with_vector([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        PlaceFactory(place_name="경복궁")
        api_client.force_authenticate(user=user)
        response = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "xyzqwerty", "sort": "recommend"})
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_no_vector_falls_back_to_popular_filter(self, api_client: APIClient) -> None:
        # 퀴즈 미완료 유저(벡터 없음)는 기존 인기순 + in-memory 필터
        user = UserFactory()
        match = PlaceFactory(place_name="제주 오름")
        PlaceFactory(place_name="남산타워")
        api_client.force_authenticate(user=user)
        response = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "제주", "sort": "recommend"})
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert match.id in ids

    def test_tag_matched_place_gets_minimum_kw_score(self, api_client: APIClient) -> None:
        # 태그명으로 매칭된 장소도 kw_score 최소값 보장 — place_name trgm이 낮아도 결과에 포함
        user = self._make_user_with_vector([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        tag = TagFactory(tag_type="세부 테마", tag_name="해수욕")
        by_tag = PlaceFactory(place_name="경포대", tags=[tag])  # place_name에 "해수욕" 없음
        PlaceFeature.objects.create(place=by_tag, style_vector=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        api_client.force_authenticate(user=user)
        response = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "해수욕", "sort": "recommend"})
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert by_tag.id in ids

    def test_zero_vector_falls_back_to_popular(self, api_client: APIClient) -> None:
        # 영벡터(퀴즈 완료했지만 결과가 0벡터)는 인기순 폴백
        travel_type = TravelTypeFactory()
        user = UserTestResultFactory(travel_type=travel_type, result_vector=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]).user
        match = PlaceFactory(place_name="한라산")
        api_client.force_authenticate(user=user)
        response = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "한라산", "sort": "recommend"})
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert match.id in ids

    def test_hybrid_pagination_page2_not_empty(self, api_client: APIClient) -> None:
        # keyword 매칭 결과가 page_size보다 많으면 page 2도 결과 반환
        user = self._make_user_with_vector([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        PlaceFactory.create_batch(12, place_name="부산 해수욕장")
        api_client.force_authenticate(user=user)
        r1 = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "부산", "sort": "recommend", "page_size": 8})
        r2 = api_client.get(PLACE_RECOMMEND_URL, {"keyword": "부산", "sort": "recommend", "page_size": 8, "page": 2})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert len(r1.data["results"]) == 8
        assert len(r2.data["results"]) == 4  # 나머지 4개
