from django.urls import path

from apps.route.views.route_views import (
    RouteDetailView,
    RouteLikeView,
    RouteListCreateView,
    UserLikedRoutesView,
    UserRouteListView,
)

urlpatterns = [
    path("routes", RouteListCreateView.as_view(), name="route-list-create"),
    path("routes/<int:route_id>", RouteDetailView.as_view(), name="route-detail"),
    path("routes/<int:route_id>/like", RouteLikeView.as_view(), name="route-like"),
    # users/routes/likes 가 users/<str:nickname>/routes 보다 먼저 등록되어야 충돌 없음
    path("users/routes/likes", UserLikedRoutesView.as_view(), name="user-liked-routes"),
    path("users/<str:nickname>/routes", UserRouteListView.as_view(), name="user-route-list"),
]
