from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.user.serializers.follow_serializer import (
    FollowActionResponseSerializer,
    FollowerListSerializer,
    FollowingListSerializer,
)

follow_post_schema = extend_schema(
    tags=["Follow"],
    summary="유저 팔로우",
    description="해당 user_id를 가진 유저를 팔로우합니다.",
    request=None,
    responses={
        201: FollowActionResponseSerializer,
        400: OpenApiResponse(description="자기 자신을 팔로우할 수 없습니다."),
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
        404: OpenApiResponse(description="사용자를 찾을 수 없습니다."),
        409: OpenApiResponse(description="이미 팔로우한 사용자입니다."),
    },
)

follow_delete_schema = extend_schema(
    tags=["Follow"],
    summary="유저 언팔로우",
    description="해당 user_id를 가진 유저를 언팔로우합니다.",
    responses={
        204: OpenApiResponse(description="언팔로우 성공"),
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
        404: OpenApiResponse(description="팔로우 관계가 없습니다."),
    },
)

followers_get_schema = extend_schema(
    tags=["Follow"],
    summary="팔로워 목록 조회",
    description="해당 user_id를 팔로우하는 사람들의 목록을 조회합니다. (커서 기반 페이지네이션)",
    responses={
        200: FollowerListSerializer,
        404: OpenApiResponse(description="사용자를 찾을 수 없습니다."),
    },
)

following_get_schema = extend_schema(
    tags=["Follow"],
    summary="팔로잉 목록 조회",
    description="해당 user_id가 팔로우하는 사람들의 목록을 조회합니다. (커서 기반 페이지네이션)",
    responses={
        200: FollowingListSerializer,
        404: OpenApiResponse(description="사용자를 찾을 수 없습니다."),
    },
)
