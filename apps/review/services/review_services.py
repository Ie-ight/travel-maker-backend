from decimal import Decimal
from typing import cast

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.db.models import Avg, Count, QuerySet

from apps.place.models import Place
from apps.review.exceptions import (
    AlreadyReviewed,
    ForbiddenReviewDelete,
    ForbiddenReviewEdit,
    PlaceNotFound,
    ReviewNotFound,
    RouteNotFound,
    RouteNotIncluded,
)
from apps.review.models import Review
from apps.route.models import Route
from apps.user.models import User, UserActionLog
from apps.user.services.action_log_service import record_action


def _get_place_or_404(place_id: int) -> Place:
    try:
        return Place.objects.get(pk=place_id)
    except Place.DoesNotExist:
        raise PlaceNotFound() from None


def _get_review_route(user: AbstractBaseUser, place_id: int, route_id: int | None) -> Route | None:
    if route_id is None:
        return None
    try:
        route = Route.objects.get(pk=route_id, user_id=user.pk)
    except Route.DoesNotExist:
        raise RouteNotFound() from None
    if not route.days.filter(day_places__place_id=place_id).exists():
        raise RouteNotIncluded()
    return route


def get_reviews(place_id: int) -> QuerySet[Review]:
    _get_place_or_404(place_id)
    return Review.objects.filter(place_id=place_id).select_related("user")


def _update_place_rating(place_id: int) -> None:
    # 호출하는 함수의 트랜잭션 안에서 실행됨
    try:
        place = Place.objects.select_for_update().get(pk=place_id)
    except Place.DoesNotExist:
        return
    result = Review.objects.filter(place_id=place_id).aggregate(avg=Avg("rating"), count=Count("id"))
    avg = result["avg"]
    place.rating_avg = Decimal(str(round(avg, 1))) if avg is not None else Decimal("0.0")  # type: ignore[assignment]
    place.rating_count = result["count"] or 0
    place.save(update_fields=["rating_avg", "rating_count"])


@transaction.atomic  # 함수 전체를 묶어, 평점 업데이트 중 오류 시 리뷰 생성도 롤백
def create_review(
    user: AbstractBaseUser,
    place_id: int,
    rating: int,
    content: str,
    image_url: str | None = None,
    route_id: int | None = None,
) -> Review:
    place = _get_place_or_404(place_id)
    if Review.objects.filter(user_id=user.pk, place_id=place_id).exists():
        raise AlreadyReviewed()
    route = _get_review_route(user, place_id, route_id)
    review = Review.objects.create(
        user_id=user.pk,
        place_id=place_id,
        rating=rating,
        content=content,
        image_url=image_url,
        route=route,
    )
    _update_place_rating(place_id)
    if rating != 3:
        record_action(cast(User, user), place, UserActionLog.ActionType.REVIEW, rating=rating)
    return review


_REVIEW_UPDATABLE_FIELDS = {"rating", "content", "image_url"}


@transaction.atomic
def update_review(user: AbstractBaseUser, review_id: int, data: dict[str, object]) -> Review:
    try:
        review = Review.objects.get(pk=review_id)
    except Review.DoesNotExist:
        raise ReviewNotFound() from None
    if review.user_id != user.pk:
        raise ForbiddenReviewEdit()

    for field, value in data.items():
        if field in _REVIEW_UPDATABLE_FIELDS:  # 허용된 필드만 수정
            setattr(review, field, value)

    fields_to_update = [f for f in data.keys() if f in _REVIEW_UPDATABLE_FIELDS]

    if "route_id" in data:
        route_id = data["route_id"]
        assert route_id is None or isinstance(route_id, int)
        review.route = _get_review_route(user, review.place_id, route_id)
        fields_to_update.append("route")

    review.save(update_fields=[*fields_to_update, "updated_at"])  # 변경된 필드 + update_at만 UPDATE
    _update_place_rating(review.place_id)
    return review


@transaction.atomic
def delete_review(user: AbstractBaseUser, review_id: int) -> None:
    try:
        review = Review.objects.get(pk=review_id)
    except Review.DoesNotExist:
        raise ReviewNotFound() from None
    if review.user_id != user.pk:
        raise ForbiddenReviewDelete()
    place_id = review.place_id
    review.delete()
    _update_place_rating(place_id)
