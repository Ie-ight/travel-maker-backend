from django.urls import path

from apps.review.views.review_views import PlaceReviewListCreateView, ReviewDetailView

urlpatterns = [
    path("places/<int:place_id>/reviews", PlaceReviewListCreateView.as_view(), name="place-review-list-create"),
    path("reviews/<int:review_id>", ReviewDetailView.as_view(), name="review-detail"),
]
