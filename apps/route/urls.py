from django.urls import path

from apps.route.views.route_views import (
    RouteDetailView,
    RouteListCreateView,
)

urlpatterns = [
    path("routes", RouteListCreateView.as_view(), name="route-list-create"),
    path("routes/<int:route_id>", RouteDetailView.as_view(), name="route-detail"),
]
