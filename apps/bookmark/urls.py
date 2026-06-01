from django.urls import path

from apps.bookmark.views import BookmarkListView

urlpatterns = [
    path("", BookmarkListView.as_view()),  # GET
]
