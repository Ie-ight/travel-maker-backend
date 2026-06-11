from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema

from apps.core.presigned_url.serializers import (
    PresignedUrlRequestSerializer,
    PresignedUrlResponseSerializer,
)
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
    description=(
        "닉네임, 한줄소개, 관심 태그, 프로필 이미지를 수정합니다.\n\n"
        "tags는 `place.Tag`의 id 목록이며, 보낸 목록으로 관심 태그 전체를 교체합니다. "
        "`GET /api/v1/tags?tag_type=세부 테마`로 전체 목록을 조회할 수 있고, "
        "현재 id는 다음과 같습니다.\n\n"
        "8: 해수욕·해안, 9: 수상레저, 10: 캠핑·글램핑, 11: 산·숲·계곡, 12: 자연생태, "
        "13: 자연공원·트레킹, 14: 랜드마크, 15: 공원·거리, 16: 쇼핑, 17: 역사·유적, "
        "18: 박물관·전시, 19: 전통체험, 20: 음식점, 21: 카페·디저트, 22: 시장·먹거리, "
        "23: 육상스포츠, 24: 항공·익스트림, 25: 테마파크·시설, 26: 스파·웰니스, 27: 숙박·리조트"
    ),
    request=ProfileUpdateSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={"nickname": "여행러버", "bio": "혼자 여행 다니는 걸 좋아해요", "tags": [8, 9, 21]},
            description="tags: 8=해수욕·해안, 9=수상레저, 21=카페·디저트",
            request_only=True,
        ),
    ],
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

profile_image_presigned_url_schema = extend_schema(
    tags=["User"],
    summary="프로필 이미지 업로드용 presigned URL 발급",
    description=(
        "프로필 이미지를 S3에 직접 업로드할 수 있는 presigned URL을 발급합니다. "
        "발급과 동시에 내 프로필의 profile_img_url이 응답의 img_url로 갱신됩니다."
    ),
    request=PresignedUrlRequestSerializer,
    responses={
        200: PresignedUrlResponseSerializer,
        400: OpenApiResponse(description="지원하지 않는 파일 형식입니다."),
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
        503: OpenApiResponse(description="이미지 업로드 URL 발급에 실패했습니다."),
    },
)
