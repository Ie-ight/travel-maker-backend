from django.db.models import Count, QuerySet
from pgvector.django import CosineDistance

from apps.place.models import Place


def get_places_sorted_by_vector(
    user_vector: list[float],
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int = 20,
) -> QuerySet[Place]:
    qs = (
        Place.objects.filter(is_active=True, place_feature__isnull=False)
        .annotate(
            distance=CosineDistance("place_feature__style_vector", user_vector),
            bookmark_count=Count("bookmarks"),
        )
        .prefetch_related("images", "tags")
        .order_by("distance")
    )

    if tag_ids:
        qs = qs.filter(tags__id__in=tag_ids).distinct()

    if region_tag_id:
        qs = qs.filter(tags__id=region_tag_id)

    return qs[:limit]


def get_popular_places(
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int = 20,
) -> QuerySet[Place]:
    """퀴즈 미완료 또는 비로그인 시 인기순 폴백."""
    qs = (
        Place.objects.filter(is_active=True)
        .annotate(bookmark_count=Count("bookmarks"))
        .prefetch_related("images", "tags")
        .order_by("-bookmark_count", "-rating_avg")
    )

    if tag_ids:
        qs = qs.filter(tags__id__in=tag_ids).distinct()

    if region_tag_id:
        qs = qs.filter(tags__id=region_tag_id)

    return qs[:limit]
