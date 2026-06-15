from django.urls import path

from apps.route.views.route_views import (
    RouteDetailView,
    RouteLikeView,
    RouteListCreateView,
)

urlpatterns = [
    path("routes", RouteListCreateView.as_view(), name="route-list-create"),
    path("routes/<int:route_id>", RouteDetailView.as_view(), name="route-detail"),
    path("routes/<int:route_id>/like", RouteLikeView.as_view(), name="route-like"),
]
