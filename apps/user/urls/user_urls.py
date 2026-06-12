from django.urls import path

from apps.user.views.follow_view import (
    FollowerListView,
    FollowingListView,
    FollowView,
)
from apps.user.views.profile_view import (
    NicknameCheckView,
    ProfileImagePresignedUrlView,
    ProfileView,
    PublicProfileView,
    PublicUserReviewView,
    UserBookmarkView,
    UserReviewView,
)

urlpatterns = [
    path("users", ProfileView.as_view(), name="profile"),
    path("users/bookmarks", UserBookmarkView.as_view(), name="user-bookmarks"),
    path("users/reviews", UserReviewView.as_view(), name="user-reviews"),
    path("users/nickname/check", NicknameCheckView.as_view(), name="nickname-check"),
    path(
        "users/profile-image/presigned-url",
        ProfileImagePresignedUrlView.as_view(),
        name="profile-image-presigned-url",
    ),
    path("users/<int:user_id>", PublicProfileView.as_view(), name="public-profile"),
    path("users/<int:user_id>/reviews", PublicUserReviewView.as_view(), name="public-user-reviews"),
    path("users/<int:user_id>/follow", FollowView.as_view(), name="user-follow"),
    path("users/<int:user_id>/followers", FollowerListView.as_view(), name="user-followers"),
    path("users/<int:user_id>/following", FollowingListView.as_view(), name="user-following"),
]
