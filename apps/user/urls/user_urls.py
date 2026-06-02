from django.urls import path

from apps.user.views.profile_view import ProfileView, UserBookmarkView, UserReviewView

urlpatterns = [
    path("users", ProfileView.as_view(), name="profile"),
    path("users/bookmarks", UserBookmarkView.as_view(), name="user-bookmarks"),
    path("users/reviews", UserReviewView.as_view(), name="user-reviews"),
]
