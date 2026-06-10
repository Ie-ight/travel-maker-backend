from django.urls import path

from apps.place.views.admin_place_views import AdminPlaceDetailView, AdminPlaceListCreateView
from apps.review.views.admin_review_views import AdminReviewDetailView, AdminReviewListView
from apps.route.views.route_views import AdminRouteDetailView
from apps.user.views.admin_view import AdminUserListView

urlpatterns = [
    path("users", AdminUserListView.as_view(), name="admin-user-list"),
    path("places", AdminPlaceListCreateView.as_view(), name="admin-place-list-create"),
    path("places/<int:place_id>", AdminPlaceDetailView.as_view(), name="admin-place-detail"),
    path("reviews", AdminReviewListView.as_view(), name="admin-review-list"),
    path("reviews/<int:review_id>", AdminReviewDetailView.as_view(), name="admin-review-detail"),
    path("routes/<int:route_id>", AdminRouteDetailView.as_view(), name="admin-route-detail"),
]
