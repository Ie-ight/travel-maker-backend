from collections.abc import Sequence

from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Count
from pgvector.django import CosineDistance

from apps.core.cache import popular_places_fallback_key
from apps.place.models import Place, PlaceFeature

_OVER_FETCH = 4
_FALLBACK_CACHE_TTL = 300


def get_places_sorted_by_vector(
    user_vector: list[float],
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int = 20,
) -> Sequence[Place]:
    # SET LOCAL은 현재 트랜잭션 스코프에만 적용된다.
    # 명시적 트랜잭션 없이 SET LOCAL을 사용하면 autocommit 모드에서
    # 각 쿼리가 별개의 트랜잭션이 되어 설정이 ANN 쿼리에 전달되지 않는다.
    with transaction.atomic():
        # iterative scan: tag 필터와 함께 HNSW 인덱스 사용 시 under-recall 방지
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL hnsw.iterative_scan = strict_order")

        pf_qs = (
            PlaceFeature.objects.filter(place__is_active=True)
            .annotate(distance=CosineDistance("style_vector", user_vector))
            .order_by("distance")
        )

        if tag_ids:
            pf_qs = pf_qs.filter(place__tags__id__in=tag_ids)
        if region_tag_id:
            pf_qs = pf_qs.filter(place__tags__id=region_tag_id)

        # M2M join으로 중복 place_id 발생 가능 — 거리 순서 유지하며 Python 중복 제거
        seen: set[int] = set()
        candidate_ids: list[int] = []
        for pid in pf_qs.values_list("place_id", flat=True)[: limit * _OVER_FETCH]:
            if pid not in seen:
                seen.add(pid)
                candidate_ids.append(pid)

    if not candidate_ids:
        return []

    places = list(
        Place.objects.filter(id__in=candidate_ids)
        .annotate(bookmark_count=Count("bookmarks", distinct=True))
        .prefetch_related("images", "tags")
    )

    # HNSW 거리 순서 복원
    order = {pid: i for i, pid in enumerate(candidate_ids)}
    return sorted(places, key=lambda p: order[p.id])[:limit]


def get_popular_places(
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int = 20,
) -> Sequence[Place]:
    """퀴즈 미완료 또는 비로그인 시 인기순 폴백. 필터 없는 경우 Redis 캐싱(300s).

    ORM 인스턴스 대신 Place ID 목록만 캐싱한다.
    모델 스키마 변경 시 역직렬화 오류가 없고 캐시 페이로드도 작다.
    """
    if not tag_ids and not region_tag_id:
        cached_ids: list[int] | None = cache.get(popular_places_fallback_key(limit))
        if cached_ids is not None:
            id_order = {pid: i for i, pid in enumerate(cached_ids)}
            cached_places = list(
                Place.objects.filter(id__in=cached_ids)
                .annotate(bookmark_count=Count("bookmarks", distinct=True))
                .prefetch_related("images", "tags")
            )
            return sorted(cached_places, key=lambda p: id_order[p.id])

    qs = (
        Place.objects.filter(is_active=True)
        .annotate(bookmark_count=Count("bookmarks", distinct=True))
        .prefetch_related("images", "tags")
        .order_by("-bookmark_count", "-rating_avg")
    )

    if tag_ids:
        qs = qs.filter(tags__id__in=tag_ids).distinct()
    if region_tag_id:
        qs = qs.filter(tags__id=region_tag_id)

    result = list(qs[:limit])

    if not tag_ids and not region_tag_id:
        cache.set(popular_places_fallback_key(limit), [p.id for p in result], _FALLBACK_CACHE_TTL)

    return result
