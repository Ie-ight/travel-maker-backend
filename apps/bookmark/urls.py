from django.urls import path

from apps.bookmark.views import BookmarkDeleteView, BookmarkListCreateView

urlpatterns = [
    path("", BookmarkListCreateView.as_view()),  # GET / POST
    path("<int:place_id>/", BookmarkDeleteView.as_view()),  # DELETE
]
