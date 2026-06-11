from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from apps.user.serializers.profile_serializer import (
    NicknameCheckResponseSerializer,
    NicknameCheckSerializer,
    ProfileSerializer,
    ProfileUpdateResponseSerializer,
    ProfileUpdateSerializer,
    PublicUserSerializer,
    UserBookmarkSerializer,
    UserReviewSerializer,
)

profile_get_schema = extend_schema(
    tags=["User"],
    summary="내 프로필 조회",
    description="로그인한 유저의 프로필 정보를 조회합니다.",
    responses={
        200: ProfileSerializer,
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
    },
)

profile_patch_schema = extend_schema(
    tags=["User"],
    summary="내 프로필 수정",
    description="닉네임, 한줄소개, 프로필 이미지를 수정합니다.",
    request=ProfileUpdateSerializer,
    responses={
        200: ProfileUpdateResponseSerializer,
        400: OpenApiResponse(description="이 필드는 필수 항목입니다."),
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
        409: OpenApiResponse(description="중복된 닉네임입니다."),
    },
)

user_bookmark_get_schema = extend_schema(
    tags=["User"],
    summary="내 북마크 목록 조회",
    description="로그인한 유저의 북마크 목록을 조회합니다.",
    parameters=[
        OpenApiParameter(name="page", type=int, required=False, description="페이지 번호"),
        OpenApiParameter(name="page_size", type=int, required=False, description="페이지 사이즈"),
    ],
    responses={
        200: UserBookmarkSerializer,
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
    },
)

user_review_get_schema = extend_schema(
    tags=["User"],
    summary="내 리뷰 목록 조회",
    description="로그인한 유저의 리뷰 목록을 조회합니다.",
    parameters=[
        OpenApiParameter(name="page", type=int, required=False, description="페이지 번호"),
        OpenApiParameter(name="page_size", type=int, required=False, description="페이지 사이즈"),
    ],
    responses={
        200: UserReviewSerializer,
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
    },
)

public_profile_get_schema = extend_schema(
    tags=["User"],
    summary="공개 프로필 조회",
    description="다른 유저의 공개 프로필 정보를 조회합니다. (이메일, 북마크/리뷰 수 미포함)",
    responses={
        200: PublicUserSerializer,
        404: OpenApiResponse(description="사용자를 찾을 수 없습니다."),
    },
)

public_user_review_get_schema = extend_schema(
    tags=["User"],
    summary="공개 리뷰 목록 조회",
    description="다른 유저가 작성한 리뷰 목록을 조회합니다.",
    parameters=[
        OpenApiParameter(name="page", type=int, required=False, description="페이지 번호"),
        OpenApiParameter(name="page_size", type=int, required=False, description="페이지 사이즈"),
    ],
    responses={
        200: UserReviewSerializer,
        404: OpenApiResponse(description="사용자를 찾을 수 없습니다."),
    },
)

nickname_check_schema = extend_schema(
    tags=["User"],
    summary="닉네임 중복 확인",
    description="닉네임 사용 가능 여부를 확인합니다.",
    request=NicknameCheckSerializer,
    responses={
        200: NicknameCheckResponseSerializer,
        400: OpenApiResponse(description="이 필드는 필수 항목입니다."),
        409: OpenApiResponse(description="중복된 닉네임이 존재합니다."),
    },
)
