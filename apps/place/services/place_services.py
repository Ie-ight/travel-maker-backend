from collections.abc import Sequence
from typing import cast

from django.contrib.postgres.search import TrigramSimilarity
from django.core.cache import cache
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Q, QuerySet, Value
from django.db.models.expressions import Combinable
from pgvector.django import CosineDistance

from apps.bookmark.models import Bookmark
from apps.place.models import Place, PlaceFeature

# review는 비정규화 컬럼 rating_count(= 리뷰 수, 리뷰 생성/수정/삭제마다 갱신)로 정렬한다.
# Count("reviews")를 bookmark_count와 함께 annotate하면 두 to-many JOIN이 곱연산으로 행을 부풀린다.
SORT_FIELDS = {"bookmark": "bookmark_count", "review": "rating_count", "rating": "rating_avg"}
TRGM_THRESHOLD = 0.15  # pg_trgm 유사도 폴백 임계값 (0.1~0.15가 폴백 티어 관행, PG 기본값 0.3)


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
            queryset = queryset.annotate(trgm_sim=TrigramSimilarity("place_name", keyword)).filter(
                trgm_sim__gt=TRGM_THRESHOLD
            )
    if tags:
        # AND 매칭: 태그별로 filter를 체이닝하면 태그마다 별도 JOIN이 생겨 "모두 포함"이 된다.
        # 각 태그 JOIN이 bookmark JOIN과 곱해질 수 있어 bookmark_count는 distinct=True로 부풀림을 막는다.
        for tag_id in tags:
            queryset = queryset.filter(tags__id=tag_id)
    field = F(SORT_FIELDS.get(sort, "bookmark_count"))
    ordering = field.asc() if order == "asc" else field.desc()
    # 정렬 기준이 동률일 때 페이지네이션이 결정적이도록 id 보조키 추가
    return queryset.order_by(ordering, "-id")


def _get_places_hybrid(
    user_vector: list[float],
    keyword: str,
    tags: list[int] | None = None,
) -> list[Place]:
    """keyword DB 필터 → 정확 코사인 유사도 → combined score 정렬.

    기존 HNSW → Python in-memory 방식은 top-N 밖 keyword 매칭을 누락한다.
    이 함수는 keyword 매칭을 DB 레벨에서 먼저 수행하고, 그 후보에 대해서만 코사인 유사도를 계산한다.
    combined = 0.7 * vec_score + 0.3 * kw_score
    페이지네이션은 뷰가 담당하므로 전체 매칭 결과를 반환한다.
    """
    base_qs = Place.objects.filter(is_active=True)
    if tags:
        for tag_id in tags:
            base_qs = base_qs.filter(tags__id=tag_id)

    # 1) keyword 후보 추출 — exists() 없이 list + truthiness로 쿼리 1회 절감
    #    "서울" 같은 광범위 키워드가 수천 건 IN(...)을 만들지 않도록 200건으로 cap
    candidate_ids = list(
        base_qs.filter(
            Q(place_name__icontains=keyword)
            | Q(tags__tag_name__icontains=keyword)
            | Q(address_primary__icontains=keyword)
        )
        .distinct()
        .values_list("id", flat=True)[:200]
    )
    exact_matched_ids: set[int] = set(candidate_ids)

    if not candidate_ids:
        # trgm 폴백 — 오타 허용
        candidate_ids = list(
            base_qs.annotate(trgm_sim=TrigramSimilarity("place_name", keyword))
            .filter(trgm_sim__gt=TRGM_THRESHOLD)
            .values_list("id", flat=True)[:200]
        )
        exact_matched_ids = set()

    if not candidate_ids:
        return []

    # 2) 후보 대상 정확 코사인 유사도 (HNSW 아닌 exact scan — 후보 수가 적어 충분히 빠름)
    dist_map: dict[int, float] = {
        row["place_id"]: float(row["distance"])
        for row in PlaceFeature.objects.filter(place_id__in=candidate_ids)
        .annotate(distance=CosineDistance("style_vector", user_vector))
        .values("place_id", "distance")
    }

    # 3) keyword relevance score — place_name trgm 유사도
    kw_map: dict[int, float] = {
        row["id"]: float(row["trgm_sim"])
        for row in Place.objects.filter(id__in=candidate_ids)
        .annotate(trgm_sim=TrigramSimilarity("place_name", keyword))
        .values("id", "trgm_sim")
    }

    # 4) place 객체 로드 (bookmark_count + prefetch)
    places: list[Place] = list(
        Place.objects.filter(id__in=candidate_ids)
        .annotate(bookmark_count=Count("bookmarks", distinct=True))
        .prefetch_related("images", "tags")
    )

    # 5) combined score 계산 후 정렬
    def combined(p: Place) -> float:
        dist = dist_map.get(p.id)
        # PlaceFeature 없는 장소는 중립값(0.5) 사용 — 0.0(반대 성향)으로 취급하지 않음
        vec_score = (1.0 - dist) if dist is not None else 0.5
        kw_score = kw_map.get(p.id, 0.0)
        # 태그/주소 exact 매칭 장소는 place_name trgm이 낮아도 최소 kw_score 보장
        if p.id in exact_matched_ids:
            kw_score = max(kw_score, 0.3)
        return 0.7 * vec_score + 0.3 * kw_score

    places.sort(key=combined, reverse=True)
    return places  # 페이지네이션은 뷰에서 처리


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

    # 영벡터는 코사인 유사도 미정의(NULL/NaN) → 인기순 폴백으로 처리
    if user_vector is not None and not any(user_vector):
        user_vector = None

    if user_vector is not None and keyword:
        # Phase 3: keyword DB 필터 후 정확 코사인 + trgm combined score
        places: list[Place] = _get_places_hybrid(user_vector, keyword, tags)
    elif user_vector is not None:
        places = list(get_places_sorted_by_vector(user_vector, tag_ids=tags or [], limit=20))
    else:
        fetch_limit = 100 if keyword else 20
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
