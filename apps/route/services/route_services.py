from typing import Any

from django.db import transaction
from django.db.models import Count, Prefetch, Q, QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

from apps.core.search import apply_trigram_filter, extract_core_keyword
from apps.place.models import Place, Tag
from apps.route.exceptions import (
    RouteForbidden,
    RouteNotFound,
    RouteValidationError,
)
from apps.route.models import Route, RouteDay, RouteDayPlace
from apps.user.models import User, UserActionLog
from apps.user.services.action_log_service import record_action


class RoutePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


def _build_prefetch() -> list[str | Prefetch]:
    # days → day_places → place → images 중첩 prefetch.
    # day_index·order 정렬로 지도 선 그리기 순서를 보장하며, 추가 쿼리 없이 좌표·이미지 접근 가능.
    return [
        "theme_tags",
        Prefetch(
            "days",
            queryset=RouteDay.objects.order_by("day_index").prefetch_related(
                Prefetch(
                    "day_places",
                    queryset=RouteDayPlace.objects.order_by("order")
                    .select_related("place")
                    .prefetch_related("place__images"),
                )
            ),
        ),
    ]


def _get_route_queryset() -> QuerySet[Route]:
    # select_related("region_tag", "user"): FK N+1 방지 (user는 상세 응답의 작성자 정보용)
    # _build_prefetch(): days·places·이미지 중첩 prefetch (목록·상세 공통)
    # annotate place_count: DB에서 총 장소 수를 한 번에 계산 (Python 루프 대신)
    return (
        Route.objects.select_related("region_tag", "user")
        .prefetch_related(*_build_prefetch())
        .annotate(place_count=Count("days__day_places", distinct=True))
    )


def _validate_days(days_data: list[dict[str, Any]], start_date: object, end_date: object) -> None:
    from datetime import date

    if not isinstance(start_date, date) or not isinstance(end_date, date):
        return
    total_days = (end_date - start_date).days + 1  # type: ignore[operator]

    # 같은 day_index가 중복으로 들어오면 RouteDay unique_together 제약에서 IntegrityError 발생
    # → 미리 차단해서 400으로 처리
    day_indexes = [day["day_index"] for day in days_data]
    if len(day_indexes) != len(set(day_indexes)):
        raise RouteValidationError(detail="day_index가 중복됩니다.")

    for day in days_data:
        day_index = day["day_index"]
        place_ids = day["place_ids"]
        # 날짜 범위를 벗어난 일차 차단 (당일치기=1일, 4박5일=5일)
        if day_index < 1 or day_index > total_days:
            raise RouteValidationError(detail=f"{day_index}일차는 유효하지 않습니다. (총 {total_days}일)")
        # 일당 장소 1~5개 제한
        if len(place_ids) < 1 or len(place_ids) > 5:
            raise RouteValidationError(detail=f"{day_index}일차 장소는 1~5개여야 합니다.")


def _validate_region_tag(region_tag_id: int) -> None:
    # 존재하지 않는 tag_id면 Route FK 제약에서 IntegrityError 발생 → 미리 400으로 처리
    from apps.place.models import Tag

    if not Tag.objects.filter(pk=region_tag_id).exists():
        raise RouteValidationError(detail="존재하지 않는 지역 태그입니다.")


def _validate_place_ids(days_data: list[dict[str, Any]]) -> None:
    # 존재하지 않는 place_id면 RouteDayPlace FK 제약에서 IntegrityError 발생 → 미리 400으로 처리
    # IN 쿼리 한 번으로 전체 일차의 장소를 한꺼번에 검증
    from apps.place.models import Place

    all_place_ids = [pid for day in days_data for pid in day["place_ids"]]
    existing_ids = set(Place.objects.filter(pk__in=all_place_ids).values_list("id", flat=True))
    missing = set(all_place_ids) - existing_ids
    if missing:
        raise RouteValidationError(detail=f"존재하지 않는 장소입니다: {sorted(missing)}")


def _create_days(route: Route, days_data: list[dict[str, Any]]) -> None:
    # RouteDay → RouteDayPlace 순서로 생성.
    # order는 place_ids 배열 인덱스 기반으로 1부터 부여 → 지도 선 그리기 순서 보장
    for day_data in days_data:
        day = RouteDay.objects.create(route=route, day_index=day_data["day_index"])
        for order, place_id in enumerate(day_data["place_ids"], start=1):
            RouteDayPlace.objects.create(route_day=day, place_id=place_id, order=order)


def _record_route_add_actions(user: User, place_ids: set[int]) -> None:
    for place in Place.objects.filter(id__in=place_ids):
        record_action(user, place, UserActionLog.ActionType.ROUTE_ADD)


def _get_route_or_404(route_id: int) -> Route:
    try:
        return Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound() from None


@transaction.atomic
def create_route(user: User, data: dict[str, Any]) -> Route:
    days_data: list[dict[str, Any]] = data.pop("days", [])
    theme_tag_ids: list[int] = data.pop("theme_tag_ids", [])
    _validate_days(days_data, data.get("start_date"), data.get("end_date"))
    _validate_region_tag(data["region_tag_id"])
    _validate_place_ids(days_data)
    route = Route.objects.create(user=user, **data)
    if theme_tag_ids:
        route.theme_tags.set(Tag.objects.filter(id__in=theme_tag_ids))
    _create_days(route, days_data)
    unique_place_ids = {pid for day_data in days_data for pid in day_data["place_ids"]}
    _record_route_add_actions(user, unique_place_ids)
    return route


@transaction.atomic
def update_route(user: User, route_id: int, data: dict[str, Any]) -> Route:
    route = _get_route_or_404(route_id)
    if route.user_id != user.pk:
        raise RouteForbidden(detail="본인이 작성한 경로만 수정할 수 있습니다.")

    days_data: list[dict[str, Any]] | None = data.pop("days", None)
    theme_tag_ids: list[int] | None = data.pop("theme_tag_ids", None)

    for field, value in data.items():
        setattr(route, field, value)
    route.save()

    if theme_tag_ids is not None:
        route.theme_tags.set(Tag.objects.filter(id__in=theme_tag_ids))

    if days_data is not None:
        start_date = route.start_date
        end_date = route.end_date
        _validate_days(days_data, start_date, end_date)
        _validate_place_ids(days_data)
        # days 수정 시 기존 일차 전체 삭제 후 재생성 (부분 수정 대신 전체 교체)
        existing_place_ids = set(
            RouteDayPlace.objects.filter(route_day__route=route).values_list("place_id", flat=True)
        )
        route.days.all().delete()
        _create_days(route, days_data)
        # 기존에 없던 장소만 ROUTE_ADD로 기록 (재기록으로 인한 행동 가중치 중복 방지)
        new_place_ids = {pid for day_data in days_data for pid in day_data["place_ids"]}
        _record_route_add_actions(user, new_place_ids - existing_place_ids)

    region_tag_id = data.get("region_tag_id")
    if region_tag_id is not None:
        _validate_region_tag(int(region_tag_id))

    return route


@transaction.atomic
def delete_route(user: User, route_id: int) -> None:
    route = _get_route_or_404(route_id)
    if route.user_id != user.pk:
        raise RouteForbidden(detail="본인이 작성한 경로만 삭제할 수 있습니다.")
    route.delete()


def get_route_detail(route_id: int) -> Route:
    # place.latitude / place.longitude 가 지도 선 그리기 핵심 좌표 데이터.
    # _get_route_queryset()을 재사용해 select_related("user") 등 목록과 동일한 최적화를 적용.
    try:
        return _get_route_queryset().get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound() from None


def _build_route_keyword_q(keyword: str) -> Q:
    """title + 지역/테마 태그명 + 핵심어 OR 조건을 반환한다."""
    core = extract_core_keyword(keyword)
    q = (
        Q(title__icontains=keyword)
        | Q(region_tag__tag_name__icontains=keyword)
        | Q(theme_tags__tag_name__icontains=keyword)
    )
    if core:
        q |= Q(title__icontains=core) | Q(region_tag__tag_name__icontains=core)
    return q


def get_routes(request: Request) -> tuple[QuerySet[Route] | None, RoutePagination]:
    qs = _get_route_queryset()

    keyword = request.query_params.get("keyword", "").strip()
    if keyword:
        filtered = qs.filter(_build_route_keyword_q(keyword)).distinct()
        # trgm 폴백: 이름 매칭 결과가 없으면 오타 허용 유사도 검색
        if not filtered.exists():
            filtered = apply_trigram_filter(qs, "title", keyword).distinct()
        qs = filtered

    region_tag_id = request.query_params.get("region_tag_id")
    if region_tag_id:
        qs = qs.filter(region_tag_id=int(region_tag_id))

    # theme_tag_ids=1&theme_tag_ids=2 또는 theme_tag_ids=1,2 모두 허용
    # 태그별로 filter 체이닝 → AND 조건 (모든 테마 태그를 포함한 경로만 조회)
    theme_tag_ids = [
        int(v) for raw in request.query_params.getlist("theme_tag_ids") for v in raw.split(",") if v.strip().isdigit()
    ]
    for tag_id in theme_tag_ids:
        qs = qs.filter(theme_tags__id=tag_id)

    ordering = request.query_params.get("ordering", "latest")
    qs = qs.order_by("-like_count", "-id") if ordering == "popular" else qs.order_by("-created_at", "-id")

    paginator = RoutePagination()
    page = paginator.paginate_queryset(qs, request)
    return page, paginator  # type: ignore[return-value]


def get_user_routes(nickname: str, request: Request) -> tuple[QuerySet[Route] | None, RoutePagination]:
    try:
        from apps.user.models import User as UserModel

        target_user = UserModel.objects.get(nickname=nickname)
    except User.DoesNotExist:
        raise RouteNotFound() from None

    qs = _get_route_queryset().filter(user=target_user).order_by("-created_at", "-id")
    paginator = RoutePagination()
    page = paginator.paginate_queryset(qs, request)
    return page, paginator  # type: ignore[return-value]


@transaction.atomic
def admin_delete_route(route_id: int) -> None:
    route = _get_route_or_404(route_id)
    route.delete()
