from typing import cast

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import AuthRequiredMixin, NotFound
from apps.core.presigned_url.views import PresignedUrlView
from apps.route.serializers.route_serializers import RouteMyListSerializer
from apps.route.services.route_services import get_user_routes
from apps.user.models import User
from apps.user.schemas.profile_schema import (
    nickname_check_schema,
    profile_get_schema,
    profile_image_presigned_url_schema,
    profile_patch_schema,
    public_profile_get_schema,
    public_user_review_get_schema,
    user_bookmark_get_schema,
    user_review_get_schema,
    user_route_list_schema,
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


class ProfileView(AuthRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]

    @profile_get_schema
    def get(self, request: Request) -> Response:
        serializer = ProfileSerializer(cast(User, request.user))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @profile_patch_schema
    @transaction.atomic
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
        profile_image_url = serializer.validated_data.pop("profile_image_url", None)
        serializer.save()

        if profile_image_url is not None:
            ProfileImageService.set_profile_image_url(user, profile_image_url)

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


class UserBookmarkView(AuthRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]

    @user_bookmark_get_schema
    def get(self, request: Request) -> Response:
        page, paginator = UserBookmarkService.get_bookmarks(cast(User, request.user), request)
        serializer = UserBookmarkSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data, status=status.HTTP_200_OK)


class UserReviewView(AuthRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]

    @user_review_get_schema
    def get(self, request: Request) -> Response:
        page, paginator = UserReviewService.get_reviews(cast(User, request.user), request)
        serializer = UserReviewSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data, status=status.HTTP_200_OK)


class UserRouteListView(APIView):
    permission_classes = [IsAuthenticated]

    @user_route_list_schema
    def get(self, request: Request, nickname: str) -> Response:
        page, paginator = get_user_routes(nickname, request)
        serializer = RouteMyListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data)


class PublicProfileView(APIView):
    permission_classes = [AllowAny]

    @public_profile_get_schema
    def get(self, request: Request, user_id: int) -> Response:
        try:
            target_user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            raise NotFound("사용자를 찾을 수 없습니다.") from None

        serializer = PublicUserSerializer(target_user, context={"request": request})
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


class ProfileImagePresignedUrlView(AuthRequiredMixin, PresignedUrlView):
    permission_classes = [IsAuthenticated]
    path = "profiles"

    @profile_image_presigned_url_schema
    def patch(self, request: Request) -> Response:
        return self.handle_request(request)
