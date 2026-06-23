from collections.abc import Sequence
from typing import Any

from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Count
from pgvector.django import CosineDistance

from apps.core.cache import popular_places_fallback_key
from apps.place.models import Place, PlaceFeature

_OVER_FETCH = 4
_FALLBACK_CACHE_TTL = 300


def _collect_vector_ids(
    pf_qs: Any,  # annotated QuerySet — generic type not expressible without stubs
    limit: int | None,
) -> list[int]:
    """HNSW 거리 순 정렬된 QuerySet에서 중복 없는 place_id 목록을 반환한다 (객체 로드 없음)."""
    seen: set[int] = set()
    candidate_ids: list[int] = []
    raw_ids = pf_qs.values_list("place_id", flat=True)
    if limit is not None:
        raw_ids = raw_ids[: limit * _OVER_FETCH]
    for pid in raw_ids:
        if pid not in seen:
            seen.add(pid)
            candidate_ids.append(pid)
    return candidate_ids


def get_place_ids_sorted_by_vector(
    user_vector: list[float],
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    offset: int = 0,
    page_size: int = 12,
) -> tuple[list[int], int]:
    """HNSW 코사인 유사도 순으로 현재 페이지 place_id 목록과 전체 count를 반환한다.

    - tag 필터 없음: DB LIMIT/OFFSET으로 정확히 page_size개만 가져옴 (가장 효율적)
    - tag 필터 있음: M2M join 중복을 피하기 위해 offset 범위까지 over-fetch 후 Python 중복 제거
    두 경우 모두 total count는 별도 COUNT 쿼리로 처리한다.
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL hnsw.iterative_scan = strict_order")

        pf_qs = (
            PlaceFeature.objects.filter(place__is_active=True, style_vector__isnull=False)
            .annotate(distance=CosineDistance("style_vector", user_vector))
            .order_by("distance")
        )

        if tag_ids:
            pf_qs = pf_qs.filter(place__tags__id__in=tag_ids)
        if region_tag_id:
            pf_qs = pf_qs.filter(place__tags__id=region_tag_id)

        has_m2m = bool(tag_ids or region_tag_id)

        # total count: tag 필터 있으면 DISTINCT COUNT로 중복 제거
        total: int = pf_qs.values("place_id").distinct().count() if has_m2m else pf_qs.count()

        if not has_m2m:
            # tag 필터 없음 → M2M join 없으므로 중복 없음, DB LIMIT/OFFSET으로 직접 처리
            page_ids = list(pf_qs.values_list("place_id", flat=True)[offset : offset + page_size])
        else:
            # tag 필터 있음 → M2M join 중복 가능, offset 범위까지 over-fetch 후 Python 중복 제거
            fetch_count = (offset + page_size) * _OVER_FETCH
            seen: set[int] = set()
            all_ids: list[int] = []
            for pid in pf_qs.values_list("place_id", flat=True)[:fetch_count]:
                if pid not in seen:
                    seen.add(pid)
                    all_ids.append(pid)
            page_ids = all_ids[offset : offset + page_size]

    return page_ids, total


def get_places_sorted_by_vector(
    user_vector: list[float],
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int | None = 20,
) -> Sequence[Place]:
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL hnsw.iterative_scan = strict_order")

        pf_qs = (
            PlaceFeature.objects.filter(place__is_active=True, style_vector__isnull=False)
            .annotate(distance=CosineDistance("style_vector", user_vector))
            .order_by("distance")
        )

        if tag_ids:
            pf_qs = pf_qs.filter(place__tags__id__in=tag_ids)
        if region_tag_id:
            pf_qs = pf_qs.filter(place__tags__id=region_tag_id)

        candidate_ids = _collect_vector_ids(pf_qs, limit)

    if not candidate_ids:
        return []

    places = list(
        Place.objects.filter(id__in=candidate_ids)
        .annotate(bookmark_count=Count("bookmarks", distinct=True))
        .prefetch_related("images", "tags")
    )

    order = {pid: i for i, pid in enumerate(candidate_ids)}
    result = sorted(places, key=lambda p: order[p.id])
    return result[:limit] if limit is not None else result


def get_places_sorted_by_content_vector(
    user_vector: list[float],
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int | None = 20,
) -> Sequence[Place]:
    """행동 기반 1024D 임베딩(content_vector) ANN 정렬 (S3, §7.2). content_vector 미생성 장소는 제외된다."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL hnsw.iterative_scan = strict_order")

        pf_qs = (
            PlaceFeature.objects.filter(place__is_active=True, content_vector__isnull=False)
            .annotate(distance=CosineDistance("content_vector", user_vector))
            .order_by("distance")
        )

        if tag_ids:
            pf_qs = pf_qs.filter(place__tags__id__in=tag_ids)
        if region_tag_id:
            pf_qs = pf_qs.filter(place__tags__id=region_tag_id)

        seen: set[int] = set()
        candidate_ids: list[int] = []
        raw_ids = pf_qs.values_list("place_id", flat=True)
        if limit is not None:
            raw_ids = raw_ids[: limit * _OVER_FETCH]
        for pid in raw_ids:
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

    order = {pid: i for i, pid in enumerate(candidate_ids)}
    result = sorted(places, key=lambda p: order[p.id])
    return result[:limit] if limit is not None else result


def get_popular_places(
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int | None = 20,
) -> Sequence[Place]:
    """퀴즈 미완료 또는 비로그인 시 인기순 폴백. 필터 없는 경우 Redis 캐싱(300s).

    ORM 인스턴스 대신 Place ID 목록만 캐싱한다.
    모델 스키마 변경 시 역직렬화 오류가 없고 캐시 페이로드도 작다.
    """
    use_cache = limit is not None and not tag_ids and not region_tag_id
    if use_cache:
        cached_ids: list[int] | None = cache.get(popular_places_fallback_key(limit))  # type: ignore[arg-type]
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
        .order_by("-bookmark_count", "-rating_avg", "-view_count")
    )

    if tag_ids:
        qs = qs.filter(tags__id__in=tag_ids).distinct()
    if region_tag_id:
        qs = qs.filter(tags__id=region_tag_id)

    result = list(qs) if limit is None else list(qs[:limit])

    if use_cache:
        cache.set(popular_places_fallback_key(limit), [p.id for p in result], _FALLBACK_CACHE_TTL)  # type: ignore[arg-type]

    return result
