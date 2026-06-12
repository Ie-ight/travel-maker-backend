from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

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
    examples=[
        OpenApiExample(
            "팔로우 성공 응답",
            value={"detail": "팔로우했습니다."},
            response_only=True,
        ),
    ],
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
    examples=[
        OpenApiExample(
            "팔로워 목록 응답",
            value={
                "next": "http://localhost:8000/api/v1/users/1/followers?cursor=cD0yMDI2LTA1LTIw",
                "previous": None,
                "results": [
                    {
                        "user_id": 2,
                        "nickname": "여행러버",
                        "profile_img_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/profiles/2_avatar.jpg",
                    },
                ],
            },
            response_only=True,
        ),
    ],
    responses={
        200: FollowerListSerializer,
        404: OpenApiResponse(description="사용자를 찾을 수 없습니다."),
    },
)

following_get_schema = extend_schema(
    tags=["Follow"],
    summary="팔로잉 목록 조회",
    description="해당 user_id가 팔로우하는 사람들의 목록을 조회합니다. (커서 기반 페이지네이션)",
    examples=[
        OpenApiExample(
            "팔로잉 목록 응답",
            value={
                "next": "http://localhost:8000/api/v1/users/1/following?cursor=cD0yMDI2LTA1LTIw",
                "previous": None,
                "results": [
                    {
                        "user_id": 3,
                        "nickname": "산악인",
                        "profile_img_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/profiles/3_avatar.jpg",
                    },
                ],
            },
            response_only=True,
        ),
    ],
    responses={
        200: FollowingListSerializer,
        404: OpenApiResponse(description="사용자를 찾을 수 없습니다."),
    },
)
