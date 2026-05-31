from django.db.models import Count, F, QuerySet

from apps.place.models import Place

SORT_FIELDS = {"bookmark": "bookmark_count", "review": "review_count", "rating": "rating_avg"}


def get_place_list(keyword: str = "", sort: str = "bookmark", order: str = "desc") -> QuerySet[Place]:
    queryset = Place.objects.prefetch_related("images", "tags").annotate(
        bookmark_count=Count("bookmarks", distinct=True),
        review_count=Count("reviews", distinct=True),
    )
    if keyword:
        queryset = queryset.filter(place_name__icontains=keyword)
    field = F(SORT_FIELDS.get(sort, "bookmark_count"))
    ordering = field.asc(nulls_last=True) if order == "asc" else field.desc(nulls_last=True)
    # 정렬 기준이 동률일 때 페이지네이션이 결정적이도록 id 보조키 추가
    return queryset.order_by(ordering, "-id")
