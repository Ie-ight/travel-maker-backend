from typing import Any

from django.db import transaction
from django.db.models import Count, F, Prefetch, QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

from apps.place.models import Tag
from apps.route.exceptions import RouteAlreadyLiked, RouteForbidden, RouteLikeNotFound, RouteNotFound
from apps.route.models import Route, RouteDay, RouteDayPlace, RouteLike
from apps.user.models import User


class RoutePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


def _get_route_queryset() -> QuerySet[Route]:
    return (
        Route.objects.select_related("region_tag")
        .prefetch_related(
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
        )
        .annotate(place_count=Count("days__day_places", distinct=True))
    )


def _validate_days(days_data: list[dict[str, Any]], start_date: object, end_date: object) -> None:
    from datetime import date

    if not isinstance(start_date, date) or not isinstance(end_date, date):
        return
    total_days = (end_date - start_date).days + 1  # type: ignore[operator]
    for day in days_data:
        day_index = day["day_index"]
        place_ids = day["place_ids"]
        if day_index < 1 or day_index > total_days:
            raise ValueError(f"{day_index}일차는 유효하지 않습니다. (총 {total_days}일)")
        if len(place_ids) < 1 or len(place_ids) > 5:
            raise ValueError(f"{day_index}일차 장소는 1~5개여야 합니다.")


def _create_days(route: Route, days_data: list[dict[str, Any]]) -> None:
    for day_data in days_data:
        day = RouteDay.objects.create(route=route, day_index=day_data["day_index"])
        for order, place_id in enumerate(day_data["place_ids"], start=1):
            RouteDayPlace.objects.create(route_day=day, place_id=place_id, order=order)


@transaction.atomic
def create_route(user: User, data: dict[str, Any]) -> Route:
    days_data: list[dict[str, Any]] = data.pop("days", [])
    theme_tag_ids: list[int] = data.pop("theme_tag_ids", [])
    _validate_days(days_data, data.get("start_date"), data.get("end_date"))
    route = Route.objects.create(user=user, **data)
    if theme_tag_ids:
        route.theme_tags.set(Tag.objects.filter(id__in=theme_tag_ids))
    _create_days(route, days_data)
    return route


@transaction.atomic
def update_route(user: User, route_id: int, data: dict[str, Any]) -> Route:
    try:
        route = Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound() from None
    if route.user_id != user.pk:
        raise RouteForbidden()

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
        route.days.all().delete()
        _create_days(route, days_data)

    return route


@transaction.atomic
def delete_route(user: User, route_id: int) -> None:
    try:
        route = Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound() from None
    if route.user_id != user.pk:
        raise RouteForbidden()
    route.delete()


def get_routes(request: Request) -> tuple[QuerySet[Route] | None, RoutePagination]:
    qs = _get_route_queryset()

    region_tag_id = request.query_params.get("region_tag_id")
    if region_tag_id:
        qs = qs.filter(region_tag_id=int(region_tag_id))

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
def like_route(user: User, route_id: int) -> RouteLike:
    try:
        route = Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound() from None
    if RouteLike.objects.filter(route=route, user=user).exists():
        raise RouteAlreadyLiked()
    like = RouteLike.objects.create(route=route, user=user)
    Route.objects.filter(pk=route_id).update(like_count=F("like_count") + 1)
    route.refresh_from_db(fields=["like_count"])
    like.route = route
    return like


@transaction.atomic
def unlike_route(user: User, route_id: int) -> None:
    try:
        route = Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound() from None
    deleted, _ = RouteLike.objects.filter(route=route, user=user).delete()
    if not deleted:
        raise RouteLikeNotFound()
    Route.objects.filter(pk=route_id).update(like_count=F("like_count") - 1)


@transaction.atomic
def admin_delete_route(route_id: int) -> None:
    try:
        route = Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound() from None
    route.delete()


def get_liked_routes(user: User, request: Request) -> tuple[QuerySet[Route] | None, RoutePagination]:
    liked_ids = RouteLike.objects.filter(user=user).values_list("route_id", flat=True)
    qs = _get_route_queryset().filter(id__in=liked_ids).order_by("-created_at", "-id")
    paginator = RoutePagination()
    page = paginator.paginate_queryset(qs, request)
    return page, paginator  # type: ignore[return-value]
