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
    UserLikedRoutesView,
    UserReviewView,
    UserRouteListView,
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
    # users/routes/likes 가 users/<str:nickname>/routes 보다 먼저 등록되어야 충돌 없음
    path("users/routes/likes", UserLikedRoutesView.as_view(), name="user-liked-routes"),
    path("users/<str:nickname>/routes", UserRouteListView.as_view(), name="user-route-list"),
    path("users/<int:user_id>", PublicProfileView.as_view(), name="public-profile"),
    path("users/<int:user_id>/reviews", PublicUserReviewView.as_view(), name="public-user-reviews"),
    path("users/<int:user_id>/follow", FollowView.as_view(), name="user-follow"),
    path("users/<int:user_id>/followers", FollowerListView.as_view(), name="user-followers"),
    path("users/<int:user_id>/following", FollowingListView.as_view(), name="user-following"),
]
