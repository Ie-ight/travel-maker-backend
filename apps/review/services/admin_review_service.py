from django.db import transaction
from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

from apps.review.exceptions import ReviewNotFound
from apps.review.models import Review
from apps.review.services.review_services import update_place_rating


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


@transaction.atomic
def admin_delete_review(review_id: int) -> None:
    try:
        review = Review.objects.get(pk=review_id)
    except Review.DoesNotExist:
        raise ReviewNotFound() from None
    place_id = review.place_id
    review.delete()
    update_place_rating(place_id)
