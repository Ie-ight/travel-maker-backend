import hashlib
from collections.abc import Sequence
from typing import cast

from django.contrib.postgres.search import TrigramSimilarity
from django.core.cache import cache
from django.db.models import BooleanField, Case, Count, Exists, F, IntegerField, Min, OuterRef, Q, QuerySet, Value, When
from django.db.models.expressions import Combinable
from pgvector.django import CosineDistance

from apps.bookmark.models import Bookmark
from apps.core.search import TRGM_THRESHOLD, extract_core_keyword
from apps.place.models import Place, PlaceFeature
from apps.place.services.feed_stage_service import determine_stage
from apps.place.services.sort_algorithm_service import (
    get_places_sorted_by_content_vector,
    get_places_sorted_by_vector,
    get_popular_places,
)
from apps.travel_quiz.models import UserTestResult
from apps.user.models import UserPreference

# review는 비정규화 컬럼 rating_count(= 리뷰 수, 리뷰 생성/수정/삭제마다 갱신)로 정렬한다.
# Count("reviews")를 bookmark_count와 함께 annotate하면 두 to-many JOIN이 곱연산으로 행을 부풀린다.
SORT_FIELDS = {"bookmark": "bookmark_count", "review": "rating_count", "rating": "rating_avg"}
HYBRID_CANDIDATE_LIMIT = 200  # IN 절 폭발 방지 상한 — 광범위 키워드 대응
VEC_WEIGHT = 0.7  # combined score 가중치: 벡터 유사도
KW_WEIGHT = 0.3  # combined score 가중치: 키워드 연관도
HYBRID_CACHE_TTL = 300  # 하이브리드 검색 sorted ID 목록 캐시 TTL (초)


def _build_name_tag_q(keyword: str) -> Q:
    """place_name + tag + 핵심어 OR 조건을 반환한다."""
    q = Q(place_name__icontains=keyword) | Q(tags__tag_name__icontains=keyword)
    core = extract_core_keyword(keyword)
    if core:
        q |= Q(place_name__icontains=core)
    return q


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
    has_relevance = False
    if keyword:
        core = extract_core_keyword(keyword)
        # tier1: place_name + tag + 핵심어(조사+접미사 제거)
        tier1_q = Q(place_name__icontains=keyword) | Q(tags__tag_name__icontains=keyword)
        if core:
            tier1_q |= Q(place_name__icontains=core)

        # _relevance: tier1 내 우선순위 — 정확 이름/태그(2) > 핵심어(1)
        relevance_whens: list[When] = [
            When(Q(place_name__icontains=keyword) | Q(tags__tag_name__icontains=keyword), then=Value(2)),
        ]
        if core:
            relevance_whens.append(When(place_name__icontains=core, then=Value(1)))

        # 단일 annotation pass로 tier + relevance를 동시에 계산 — exists() 이중 쿼리 제거
        annotated = (
            queryset.annotate(
                _tier=Case(
                    When(tier1_q, then=Value(1)),
                    When(address_primary__icontains=keyword, then=Value(2)),
                    default=Value(99),
                    output_field=IntegerField(),
                ),
                _relevance=Case(*relevance_whens, default=Value(0), output_field=IntegerField()),
            )
            .filter(_tier__lt=99)
            .distinct()
        )

        # aggregate(Min)으로 어느 tier에 결과가 있는지 1 query로 확인
        best_tier: int | None = annotated.aggregate(best_tier=Min("_tier"))["best_tier"]
        if best_tier is not None:
            queryset = annotated.filter(_tier=best_tier)
            has_relevance = True
        else:
            # 3단계: trgm 폴백 — 오타 허용
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
    # 관련성 있는 경우: tier1 내에서 _relevance 우선 → 요청 정렬 → id 보조키
    if has_relevance:
        return queryset.order_by("-_relevance", ordering, "-id")
    return queryset.order_by(ordering, "-id")


def _hybrid_cache_key(keyword: str, tags: list[int] | None, user_vector: list[float]) -> str:
    vec_str = ",".join(f"{v:.4f}" for v in user_vector)
    tags_str = ",".join(str(t) for t in sorted(tags or []))
    payload = f"{keyword}|{tags_str}|{vec_str}"
    return f"hybrid_ids:{hashlib.md5(payload.encode()).hexdigest()}"  # noqa: S324


def _get_places_hybrid(
    user_vector: list[float],
    keyword: str,
    tags: list[int] | None = None,
    vector_field: str = "style_vector",
) -> list[Place]:
    """keyword DB 필터 → 정확 코사인 유사도 → combined score 정렬.

    기존 HNSW → Python in-memory 방식은 top-N 밖 keyword 매칭을 누락한다.
    이 함수는 keyword 매칭을 DB 레벨에서 먼저 수행하고, 그 후보에 대해서만 코사인 유사도를 계산한다.
    combined = 0.7 * vec_score + 0.3 * kw_score
    vector_field: S2는 "style_vector"(6D), S3는 "content_vector"(1024D)를 사용한다.
    페이지네이션은 뷰가 담당하므로 전체 매칭 결과를 반환한다.
    """
    # sorted ID 목록을 캐시 — 동일 (keyword, tags, vector) 요청은 재계산 없이 재사용
    cache_key = _hybrid_cache_key(keyword, tags, user_vector)
    cached_ids: list[int] | None = cache.get(cache_key)
    if cached_ids is not None:
        place_map = {
            p.id: p
            for p in Place.objects.filter(id__in=cached_ids)
            .annotate(bookmark_count=Count("bookmarks", distinct=True))
            .prefetch_related("images", "tags")
        }
        return [place_map[pid] for pid in cached_ids if pid in place_map]

    base_qs = Place.objects.filter(is_active=True)
    if tags:
        for tag_id in tags:
            base_qs = base_qs.filter(tags__id=tag_id)

    # 1단계: place_name + tag + 핵심어 매칭 — rating_avg 우선 정렬 후 cap
    candidate_ids = list(
        base_qs.filter(_build_name_tag_q(keyword))
        .distinct()
        .order_by("-rating_avg")
        .values_list("id", flat=True)[:HYBRID_CANDIDATE_LIMIT]
    )
    exact_matched_ids: set[int] = set(candidate_ids)
    prefetched_kw_map: dict[int, float] = {}
    is_trgm_fallback = False

    if not candidate_ids:
        # 2단계: 주소 매칭 — 해당 거리·지역에 위치한 장소
        candidate_ids = list(
            base_qs.filter(address_primary__icontains=keyword)
            .distinct()
            .order_by("-rating_avg")
            .values_list("id", flat=True)[:HYBRID_CANDIDATE_LIMIT]
        )
        exact_matched_ids = set(candidate_ids)

    if not candidate_ids:
        # 3단계: trgm 폴백 — 오타 허용, trgm_sim을 kw_map에 재사용해 중복 쿼리 제거
        trgm_rows = list(
            base_qs.annotate(trgm_sim=TrigramSimilarity("place_name", keyword))
            .filter(trgm_sim__gt=TRGM_THRESHOLD)
            .order_by("-trgm_sim")
            .values("id", "trgm_sim")[:HYBRID_CANDIDATE_LIMIT]
        )
        candidate_ids = [row["id"] for row in trgm_rows]
        prefetched_kw_map = {row["id"]: float(row["trgm_sim"]) for row in trgm_rows}
        is_trgm_fallback = True
        exact_matched_ids = set()

    if not candidate_ids:
        return []

    # 2) 후보 대상 정확 코사인 유사도 (HNSW 아닌 exact scan — 후보 수가 적어 충분히 빠름)
    dist_map: dict[int, float] = {
        row["place_id"]: float(row["distance"])
        for row in PlaceFeature.objects.filter(place_id__in=candidate_ids, **{f"{vector_field}__isnull": False})
        .annotate(distance=CosineDistance(vector_field, user_vector))
        .values("place_id", "distance")
    }

    # 3) keyword relevance score — trgm 폴백이면 이미 계산된 값 재사용 (명시적 플래그로 빈 dict 혼동 방지)
    kw_map: dict[int, float] = (
        prefetched_kw_map
        if is_trgm_fallback
        else {
            row["id"]: float(row["trgm_sim"])
            for row in Place.objects.filter(id__in=candidate_ids)
            .annotate(trgm_sim=TrigramSimilarity("place_name", keyword))
            .values("id", "trgm_sim")
        }
    )

    # 4) dict 기반 combined score로 id 정렬 — Place 객체 로드 전 순서 확정
    def score(place_id: int) -> float:
        dist = dist_map.get(place_id)
        # CosineDistance는 [0,2] 범위(= 1 - cosine_sim). /2로 [0,1] 정규화하면
        # 중립값 0.5 = cosine_sim 0(무관계)와 스케일이 일치한다.
        # PlaceFeature 없는 장소는 중립값(0.5) 사용 — 0.0(반대 성향)으로 취급하지 않음
        vec_score = (1.0 - dist / 2.0) if dist is not None else 0.5
        kw_score = kw_map.get(place_id, 0.0)
        # 태그/주소 exact 매칭 장소는 place_name trgm이 낮아도 최소 kw_score 보장
        if place_id in exact_matched_ids:
            kw_score = max(kw_score, 0.3)
        return VEC_WEIGHT * vec_score + KW_WEIGHT * kw_score

    sorted_ids = sorted(candidate_ids, key=score, reverse=True)
    cache.set(cache_key, sorted_ids, timeout=HYBRID_CACHE_TTL)

    # 5) 정렬된 순서로 Place 객체 로드 — IN 쿼리는 순서 비보장이므로 dict 경유 재정렬
    place_map = {
        p.id: p
        for p in Place.objects.filter(id__in=sorted_ids)
        .annotate(bookmark_count=Count("bookmarks", distinct=True))
        .prefetch_related("images", "tags")
    }
    return [place_map[pid] for pid in sorted_ids if pid in place_map]


_REMAINING_CAP = 500  # 전체 장소를 메모리에 올리지 않기 위한 인기순 보충 상한


def _append_remaining(vector_places: list[Place], tags: list[int] | None) -> list[Place]:
    """벡터 정렬 결과 뒤에 벡터 미적용 나머지 장소를 인기순 상위 _REMAINING_CAP개로 이어 붙인다."""
    vector_ids = {p.id for p in vector_places}
    remaining_qs = (
        Place.objects.filter(is_active=True)
        .exclude(id__in=vector_ids)
        .annotate(bookmark_count=Count("bookmarks", distinct=True))
        .prefetch_related("images", "tags")
        .order_by("-bookmark_count", "-rating_avg", "-view_count")
    )
    if tags:
        for tag_id in tags:
            remaining_qs = remaining_qs.filter(tags__id=tag_id)
    return vector_places + list(remaining_qs[:_REMAINING_CAP])


def get_place_list_recommend(
    user_id: int | None,
    keyword: str = "",
    tags: list[int] | None = None,
) -> Sequence[Place]:
    """S1(인기)/S2(퀴즈 6축 ANN)/S3(행동 기반 1024D ANN) 단계별 추천순."""
    stage = determine_stage(user_id)

    user_vector: list[float] | None = None
    vector_field = "style_vector"
    if stage == "S3":
        assert user_id is not None  # S3는 determine_stage가 로그인 유저에게만 반환
        preference = UserPreference.objects.get(user_id=user_id)
        user_vector = list(preference.content_vector)
        vector_field = "content_vector"
    elif stage == "S2":
        assert user_id is not None  # S2도 로그인 유저에게만 반환
        result = UserTestResult.objects.get(user_id=user_id)
        user_vector = list(result.result_vector)

    # 영벡터는 코사인 유사도 미정의(NULL/NaN) → 인기순 폴백으로 처리
    if user_vector is not None and not any(user_vector):
        user_vector = None

    places: list[Place]
    if user_vector is not None and keyword:
        # Phase 3: keyword DB 필터 후 정확 코사인 + trgm combined score
        places = _get_places_hybrid(user_vector, keyword, tags, vector_field=vector_field)
    elif user_vector is not None and vector_field == "content_vector":
        # 벡터 매칭 장소 전체 → 나머지를 인기순으로 이어 붙임
        vector_places = list(get_places_sorted_by_content_vector(user_vector, tag_ids=tags or [], limit=None))
        places = _append_remaining(vector_places, tags)
    elif user_vector is not None:
        # 벡터 매칭 장소 전체 → 나머지를 인기순으로 이어 붙임
        vector_places = list(get_places_sorted_by_vector(user_vector, tag_ids=tags or [], limit=None))
        places = _append_remaining(vector_places, tags)
    else:
        if keyword:
            popular = list(get_popular_places(tag_ids=tags or [], limit=100))
            kw = keyword.lower()
            core = extract_core_keyword(keyword)
            core_lower = core.lower() if core else None

            # DB 경로와 동일한 계층 우선순위 적용 — 주소는 이름/태그 미매칭 시에만 폴백
            tier1 = [
                p
                for p in popular
                if kw in p.place_name.lower()
                or any(kw in t.tag_name.lower() for t in p.tags.all())
                or (core_lower and core_lower in p.place_name.lower())
            ]
            places = tier1 or [p for p in popular if p.address_primary and kw in p.address_primary.lower()]
        else:
            # 비로그인/퀴즈 미완료: 인기순 상위 _REMAINING_CAP개
            places = list(get_popular_places(tag_ids=tags or [], limit=_REMAINING_CAP))

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


def increment_view_count(place_id: int) -> None:
    # F() 원자 증가 — 동시 요청에도 갱신 누락 없음. 응답 객체의 view_count는 갱신되지 않으나
    # 시리얼라이저가 view_count를 노출하지 않으므로 별도 refresh 불필요.
    Place.objects.filter(pk=place_id).update(view_count=F("view_count") + 1)
