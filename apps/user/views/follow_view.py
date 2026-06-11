from typing import Never, cast

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import NotFound
from apps.user.models import User
from apps.user.schemas.follow_schema import (
    follow_delete_schema,
    follow_post_schema,
    followers_get_schema,
    following_get_schema,
)
from apps.user.serializers.follow_serializer import (
    FollowerListSerializer,
    FollowingListSerializer,
)
from apps.user.services.follow_service import FollowCursorPagination, FollowService


class FollowView(APIView):
    permission_classes = [IsAuthenticated]

    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> Never:
        raise NotAuthenticated("자격 인증 데이터가 제공되지 않았습니다.")

    @follow_post_schema
    def post(self, request: Request, user_id: int) -> Response:
        FollowService.follow(cast(User, request.user), user_id)
        return Response({"detail": "팔로우했습니다."}, status=status.HTTP_201_CREATED)

    @follow_delete_schema
    def delete(self, request: Request, user_id: int) -> Response:
        FollowService.unfollow(cast(User, request.user), user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowerListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = FollowCursorPagination

    @followers_get_schema
    def get(self, request: Request, user_id: int) -> Response:
        if not User.objects.filter(id=user_id, is_active=True).exists():
            raise NotFound("사용자를 찾을 수 없습니다.")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(FollowService.get_followers(user_id), request)
        serializer = FollowerListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data, status=status.HTTP_200_OK)


class FollowingListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = FollowCursorPagination

    @following_get_schema
    def get(self, request: Request, user_id: int) -> Response:
        if not User.objects.filter(id=user_id, is_active=True).exists():
            raise NotFound("사용자를 찾을 수 없습니다.")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(FollowService.get_following(user_id), request)
        serializer = FollowingListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data, status=status.HTTP_200_OK)
