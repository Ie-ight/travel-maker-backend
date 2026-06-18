from django.db import IntegrityError
from django.db.models import QuerySet
from rest_framework.pagination import CursorPagination

from apps.core.exceptions import BadRequest, Conflict, NotFound
from apps.user.models import Follow, User


class FollowCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"


class FollowService:
    @staticmethod
    def follow(follower: User, target_user_id: int) -> None:
        if follower.id == target_user_id:
            raise BadRequest("자기 자신을 팔로우할 수 없습니다.")
        if not User.objects.filter(id=target_user_id, is_active=True).exists():
            raise NotFound("사용자를 찾을 수 없습니다.")
        try:
            Follow.objects.create(follower=follower, following_id=target_user_id)
        except IntegrityError:
            raise Conflict("이미 팔로우한 사용자입니다.") from None

    @staticmethod
    def unfollow(follower: User, target_user_id: int) -> None:
        deleted, _ = Follow.objects.filter(follower=follower, following_id=target_user_id).delete()
        if not deleted:
            raise NotFound("팔로우 관계가 없습니다.")

    @staticmethod
    def get_followers(user_id: int) -> QuerySet[Follow]:
        # following == user_id 인 행 = user_id를 팔로우하는 사람들 = user_id의 팔로워 목록
        return Follow.objects.filter(following_id=user_id).select_related("follower").order_by("-created_at")

    @staticmethod
    def get_following(user_id: int) -> QuerySet[Follow]:
        # follower == user_id 인 행 = user_id가 팔로우하는 사람들 = user_id의 팔로잉 목록
        return Follow.objects.filter(follower_id=user_id).select_related("following").order_by("-created_at")
