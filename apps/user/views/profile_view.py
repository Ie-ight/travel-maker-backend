from typing import Never, cast

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import NotFound
from apps.user.models import User
from apps.user.schemas.profile_schema import (
    nickname_check_schema,
    profile_get_schema,
    profile_patch_schema,
    public_profile_get_schema,
    public_user_review_get_schema,
    user_bookmark_get_schema,
    user_review_get_schema,
)
from apps.user.serializers.profile_serializer import (
    NicknameCheckSerializer,
    ProfileSerializer,
    ProfileUpdateResponseSerializer,
    ProfileUpdateSerializer,
    PublicUserSerializer,
    UserBookmarkSerializer,
    UserReviewSerializer,
)
from apps.user.services.profile_service import (
    NicknameService,
    ProfileImageService,
    UserBookmarkService,
    UserReviewService,
)


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
        if nickname:
            NicknameService.check_available(nickname, exclude_user=user)
        serializer = ProfileUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        profile_image = serializer.validated_data.pop("profile_image", None)
        serializer.save()

        if profile_image is not None:
            ProfileImageService.queue_upload(user, profile_image)

        response_serializer = ProfileUpdateResponseSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class NicknameCheckView(APIView):
    permission_classes = [AllowAny]

    @nickname_check_schema
    def post(self, request: Request) -> Response:
        serializer = NicknameCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        NicknameService.check_available(serializer.validated_data["nickname"])

        return Response({"detail": "사용가능한 닉네임 입니다."}, status=status.HTTP_200_OK)


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


class PublicProfileView(APIView):
    permission_classes = [AllowAny]

    @public_profile_get_schema
    def get(self, request: Request, user_id: int) -> Response:
        try:
            target_user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            raise NotFound("사용자를 찾을 수 없습니다.") from None

        serializer = PublicUserSerializer(target_user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicUserReviewView(APIView):
    permission_classes = [AllowAny]

    @public_user_review_get_schema
    def get(self, request: Request, user_id: int) -> Response:
        try:
            target_user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            raise NotFound("사용자를 찾을 수 없습니다.") from None

        page, paginator = UserReviewService.get_reviews(target_user, request)
        serializer = UserReviewSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data, status=status.HTTP_200_OK)
