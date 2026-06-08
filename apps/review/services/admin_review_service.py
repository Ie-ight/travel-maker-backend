from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

from apps.place.models import Place
from apps.review.exceptions import ReviewNotFound
from apps.review.models import Review


class AdminReviewPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def get_admin_reviews(request: Request) -> tuple[QuerySet[Review] | None, AdminReviewPagination]:
    qs = Review.objects.select_related("user", "place").order_by("-id")
    place_id = request.query_params.get("place_id")
    if place_id:
        qs = qs.filter(place_id=place_id)
    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)
    paginator = AdminReviewPagination()
    page = paginator.paginate_queryset(qs, request)
    return page, paginator  # type: ignore[return-value]


def _update_place_rating(place_id: int) -> None:
    try:
        place = Place.objects.select_for_update().get(pk=place_id)
    except Place.DoesNotExist:
        return
    result = Review.objects.filter(place_id=place_id).aggregate(avg=Avg("rating"), count=Count("id"))
    avg = result["avg"]
    place.rating_avg = Decimal(str(round(avg, 1))) if avg is not None else Decimal("0.0")  # type: ignore[assignment]
    place.rating_count = result["count"] or 0
    place.save(update_fields=["rating_avg", "rating_count"])


@transaction.atomic
def admin_delete_review(review_id: int) -> None:
    try:
        review = Review.objects.get(pk=review_id)
    except Review.DoesNotExist:
        raise ReviewNotFound() from None
    place_id = review.place_id
    review.delete()
    _update_place_rating(place_id)
