from django.urls import path

from apps.place.views import place_views

urlpatterns = [
    path("", place_views.PlaceListView.as_view(), name="place_list"),
    path("search", place_views.PlaceSearchView.as_view(), name="place_search"),
    path("filter", place_views.PlaceFilterView.as_view(), name="place_filter"),
    path("<int:place_id>", place_views.PlaceDetailView.as_view(), name="place_detail"),
]
