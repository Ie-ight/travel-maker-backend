from collections.abc import Sequence
from typing import cast

from django.contrib.postgres.search import TrigramSimilarity
from django.core.cache import cache
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Q, QuerySet, Value
from django.db.models.expressions import Combinable

from apps.bookmark.models import Bookmark
from apps.place.models import Place

# review는 비정규화 컬럼 rating_count(= 리뷰 수, 리뷰 생성/수정/삭제마다 갱신)로 정렬한다.
# Count("reviews")를 bookmark_count와 함께 annotate하면 두 to-many JOIN이 곱연산으로 행을 부풀린다.
SORT_FIELDS = {"bookmark": "bookmark_count", "review": "rating_count", "rating": "rating_avg"}


def _is_bookmarked_expr(user_id: int | None) -> Combinable:
    # 비로그인은 서브쿼리 없이 상수 False (Exists를 안 거니까 SQL도 가볍다)
    if user_id is None:
        return Value(False, output_field=BooleanField())
    return Exists(Bookmark.objects.filter(place=OuterRef("pk"), user_id=user_id))


def get_place_list(
    keyword: str = "",
    sort: str = "bookmark",
    order: str = "desc",
    tags: list[int] | None = None,
    user_id: int | None = None,
) -> QuerySet[Place]:
    # is_active=False는 증분 동기화(단계 7)에서 소프트삭제된 장소 → 목록에서 제외
    queryset = (
        Place.objects.filter(is_active=True)
        .prefetch_related("images", "tags")
        .annotate(bookmark_count=Count("bookmarks", distinct=True), is_bookmarked=_is_bookmarked_expr(user_id))
    )
    if keyword:
        exact_qs = queryset.filter(
            Q(place_name__icontains=keyword)
            | Q(tags__tag_name__icontains=keyword)
            | Q(address_primary__icontains=keyword)
        ).distinct()
        if exact_qs.exists():
            queryset = exact_qs
        else:
            # 정확 매칭 결과 없으면 place_name 트라이그램 유사도 폴백 (오타 허용)
            queryset = queryset.annotate(trgm_sim=TrigramSimilarity("place_name", keyword)).filter(trgm_sim__gt=0.15)
    if tags:
        # AND 매칭: 태그별로 filter를 체이닝하면 태그마다 별도 JOIN이 생겨 "모두 포함"이 된다.
        # 각 태그 JOIN이 bookmark JOIN과 곱해질 수 있어 bookmark_count는 distinct=True로 부풀림을 막는다.
        for tag_id in tags:
            queryset = queryset.filter(tags__id=tag_id)
    field = F(SORT_FIELDS.get(sort, "bookmark_count"))
    ordering = field.asc() if order == "asc" else field.desc()
    # 정렬 기준이 동률일 때 페이지네이션이 결정적이도록 id 보조키 추가
    return queryset.order_by(ordering, "-id")


def get_place_list_recommend(
    user_id: int | None,
    keyword: str = "",
    tags: list[int] | None = None,
) -> Sequence[Place]:
    """유저 성향 벡터 기반 추천순. 벡터 없으면 인기순 폴백."""
    from apps.place.services.sort_algorithm_service import get_places_sorted_by_vector, get_popular_places
    from apps.travel_quiz.models import UserTestResult

    user_vector: list[float] | None = None
    if user_id is not None:
        try:
            result = UserTestResult.objects.get(user_id=user_id)
            user_vector = list(result.result_vector)
        except UserTestResult.DoesNotExist:
            pass

    # 키워드 필터가 있으면 in-memory 필터링을 위해 넉넉히 가져온다
    fetch_limit = 100 if keyword else 20
    if user_vector is not None:
        places = list(get_places_sorted_by_vector(user_vector, tag_ids=tags or [], limit=fetch_limit))
    else:
        places = list(get_popular_places(tag_ids=tags or [], limit=fetch_limit))

    if keyword:
        kw = keyword.lower()
        places = [
            p
            for p in places
            if kw in p.place_name.lower()
            or any(kw in t.tag_name.lower() for t in p.tags.all())
            or (p.address_primary and kw in p.address_primary.lower())
        ]

    # PlaceListSerializer의 is_bookmarked 필드 요구에 맞게 Python 레벨에서 채운다 (쿼리 1회)
    if user_id is not None and places:
        bookmarked_ids = set(
            Bookmark.objects.filter(user_id=user_id, place_id__in=[p.id for p in places]).values_list(
                "place_id", flat=True
            )
        )
        for place in places:
            place.is_bookmarked = place.id in bookmarked_ids  # type: ignore[attr-defined]
    else:
        for place in places:
            place.is_bookmarked = False  # type: ignore[attr-defined]

    return places


def get_place_detail(place_id: int, user_id: int | None = None) -> Place | None:
    # 없으면 None 반환(순수 데이터 접근). "없으면 404" 판단은 뷰가 한다.
    # review_count는 비정규화 rating_count 컬럼에서 직접 읽고(시리얼라이저 source), bookmark_count는
    # 상세에서 노출하지 않으므로 런타임 집계(JOIN)가 전혀 없다.
    cache_key = f"place_detail:{place_id}"
    place = cast(Place | None, cache.get(cache_key))

    if place is None:
        place = (
            Place.objects.select_related("info")
            .prefetch_related("images", "tags")
            .filter(id=place_id, is_active=True)
            .first()
        )
        if place is not None:
            cache.set(cache_key, place, 60 * 60)

    if place is not None:
        # is_bookmarked는 캐시 없이 별도 조회
        place.is_bookmarked = (  # type: ignore[attr-defined]
            Bookmark.objects.filter(place_id=place_id, user_id=user_id).exists() if user_id else False
        )

    return place
