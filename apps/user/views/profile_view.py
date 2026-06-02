from typing import Never, cast

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import Conflict
from apps.user.models import User
from apps.user.schemas.profile_schema import (
    profile_get_schema,
    profile_patch_schema,
    user_bookmark_get_schema,
    user_review_get_schema,
)
from apps.user.serializers.profile_serializer import (
    ProfileSerializer,
    ProfileUpdateResponseSerializer,
    ProfileUpdateSerializer,
    UserBookmarkSerializer,
    UserReviewSerializer,
)
from apps.user.services.profile_service import UserBookmarkService, UserReviewService


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> Never:
        raise NotAuthenticated("자격 인증 데이터가 제공되지 않았습니다.")

    @profile_get_schema
    def get(self, request: Request) -> Response:
        serializer = ProfileSerializer(cast(User, request.user))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @profile_patch_schema
    def patch(self, request: Request) -> Response:
        user = cast(User, request.user)
        nickname = request.data.get("nickname")
        if nickname and User.objects.filter(nickname=nickname).exclude(pk=user.pk).exists():
            raise Conflict("중복된 닉네임입니다.")
        serializer = ProfileUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = ProfileUpdateResponseSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class UserBookmarkView(APIView):
    permission_classes = [IsAuthenticated]

    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> Never:
        raise NotAuthenticated("자격 인증 데이터가 제공되지 않았습니다.")

    @user_bookmark_get_schema
    def get(self, request: Request) -> Response:
        page, paginator = UserBookmarkService.get_bookmarks(cast(User, request.user), request)
        serializer = UserBookmarkSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data, status=status.HTTP_200_OK)


class UserReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> Never:
        raise NotAuthenticated("자격 인증 데이터가 제공되지 않았습니다.")

    @user_review_get_schema
    def get(self, request: Request) -> Response:
        page, paginator = UserReviewService.get_reviews(cast(User, request.user), request)
        serializer = UserReviewSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data, status=status.HTTP_200_OK)
