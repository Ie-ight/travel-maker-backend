from django.db.models import BooleanField, Count, Exists, F, OuterRef, QuerySet, Value
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
        queryset = queryset.filter(place_name__icontains=keyword)
    if tags:
        # AND 매칭: 태그별로 filter를 체이닝하면 태그마다 별도 JOIN이 생겨 "모두 포함"이 된다.
        # 각 태그 JOIN이 bookmark JOIN과 곱해질 수 있어 bookmark_count는 distinct=True로 부풀림을 막는다.
        for tag_id in tags:
            queryset = queryset.filter(tags__id=tag_id)
    field = F(SORT_FIELDS.get(sort, "bookmark_count"))
    ordering = field.asc() if order == "asc" else field.desc()
    # 정렬 기준이 동률일 때 페이지네이션이 결정적이도록 id 보조키 추가
    return queryset.order_by(ordering, "-id")


def get_place_detail(place_id: int, user_id: int | None = None) -> Place | None:
    # 없으면 None 반환(순수 데이터 접근). "없으면 404" 판단은 뷰가 한다.
    # review_count는 비정규화 rating_count 컬럼에서 직접 읽고(시리얼라이저 source), bookmark_count는
    # 상세에서 노출하지 않으므로 런타임 집계(JOIN)가 전혀 없다.
    return (
        Place.objects.select_related("info")  # 운영정보(PlaceInfo, 역방향 1:1) — 상세 detail용
        .prefetch_related("images", "tags")
        .annotate(is_bookmarked=_is_bookmarked_expr(user_id))
        .filter(id=place_id, is_active=True)  # 소프트삭제 장소는 상세도 미노출(뷰에서 404)
        .first()
    )
