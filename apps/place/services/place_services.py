from django.db.models import Count, F, QuerySet

from apps.place.models import Place

SORT_FIELDS = {"bookmark": "bookmark_count", "review": "review_count", "rating": "rating_avg"}


def get_place_list(
    keyword: str = "",
    sort: str = "bookmark",
    order: str = "desc",
    tags: list[int] | None = None,
) -> QuerySet[Place]:
    queryset = Place.objects.prefetch_related("images", "tags").annotate(
        bookmark_count=Count("bookmarks", distinct=True),
        review_count=Count("reviews", distinct=True),
    )
    if keyword:
        queryset = queryset.filter(place_name__icontains=keyword)
    if tags:
        # AND 매칭: 태그별로 filter를 체이닝하면 태그마다 별도 JOIN이 생겨 "모두 포함"이 된다.
        # 각 JOIN이 동시에 만족되어야 하므로 Place 행 중복이 없고(distinct 불필요),
        # bookmark_count/review_count도 distinct=True 덕분에 부풀려지지 않는다.
        for tag_id in tags:
            queryset = queryset.filter(tags__id=tag_id)
    field = F(SORT_FIELDS.get(sort, "bookmark_count"))
    ordering = field.asc() if order == "asc" else field.desc()
    # 정렬 기준이 동률일 때 페이지네이션이 결정적이도록 id 보조키 추가
    return queryset.order_by(ordering, "-id")


def get_place_detail(place_id: int) -> Place | None:
    # 없으면 None 반환(순수 데이터 접근). "없으면 404" 판단은 뷰가 한다.
    return (
        Place.objects.prefetch_related("images", "tags")
        .annotate(
            # bookmark/review를 동시에 annotate하면 distinct 없이는 곱연산으로 부풀려진다
            bookmark_count=Count("bookmarks", distinct=True),
            review_count=Count("reviews", distinct=True),
        )
        .filter(id=place_id)
        .first()
    )
