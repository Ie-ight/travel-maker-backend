from django.urls import path

from apps.review import views

urlpatterns = [
    path("places/<str:place_id>/reviews", views.PlaceReviewListCreateView.as_view(), name="place-review-list-create"),
    path("reviews/<int:review_id>", views.ReviewDetailView.as_view(), name="review-detail"),
]
