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
    examples=[
        OpenApiExample(
            "내 프로필 응답",
            value={
                "id": 1,
                "nickname": "여행러버",
                "bio": "혼자 여행 다니는 걸 좋아해요",
                "email": "traveler@example.com",
                "profile_img_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/profiles/1_avatar.jpg",
                "tags": [
                    {"id": 8, "name": "해수욕·해안"},
                    {"id": 21, "name": "카페·디저트"},
                ],
                "follower_count": 12,
                "following_count": 8,
                "bookmark_count": 5,
                "review_count": 3,
                "travel_type_name": "감성 여행가",
                "created_at": "2026-01-10T09:00:00Z",
                "updated_at": "2026-05-22T12:23:11Z",
            },
            response_only=True,
        ),
    ],
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
        "23: 육상스포츠, 24: 항공·익스트림, 25: 테마파크·시설, 26: 스파·웰니스, 27: 숙박·리조트\n\n"
        "profile_image_url은 `/users/profile-image/presigned-url`로 발급받은 img_url을 그대로 담아 보내세요."
    ),
    request=ProfileUpdateSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={
                "nickname": "여행러버",
                "bio": "혼자 여행 다니는 걸 좋아해요",
                "tags": [8, 9, 21],
                "profile_image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/profiles/uuid_avatar.jpg",
            },
            description="tags: 8=해수욕·해안, 9=수상레저, 21=카페·디저트",
            request_only=True,
        ),
        OpenApiExample(
            "수정 응답 예시",
            value={
                "nickname": "여행러버",
                "bio": "혼자 여행 다니는 걸 좋아해요",
                "profile_img_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/profiles/1_avatar.jpg",
                "tags": [
                    {"id": 8, "name": "해수욕·해안"},
                    {"id": 9, "name": "수상레저"},
                    {"id": 21, "name": "카페·디저트"},
                ],
                "created_at": "2026-01-10T09:00:00Z",
                "updated_at": "2026-05-22T12:23:11Z",
            },
            response_only=True,
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
    examples=[
        OpenApiExample(
            "내 북마크 목록 응답",
            value={
                "count": 17,
                "next": "http://localhost:8000/api/v1/users/bookmarks?page=2",
                "previous": None,
                "results": [
                    {
                        "place_id": 1,
                        "place_name": "부산 광안리 해수욕장",
                        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/places/img.jpg",
                        "rating": 4.5,
                        "created_at": "2026-05-22T12:23:11Z",
                    },
                ],
            },
            response_only=True,
        ),
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
    examples=[
        OpenApiExample(
            "내 리뷰 목록 응답",
            value={
                "count": 9,
                "next": "http://localhost:8000/api/v1/users/reviews?page=2",
                "previous": None,
                "results": [
                    {
                        "review_id": 1,
                        "place_id": 1,
                        "place_name": "부산 광안리 해수욕장",
                        "rating": 5,
                        "content": "야경이 정말 예뻐요!",
                        "created_at": "2026-05-22T12:23:11Z",
                        "updated_at": "2026-05-22T12:23:11Z",
                    },
                ],
            },
            response_only=True,
        ),
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
    examples=[
        OpenApiExample(
            "공개 프로필 응답",
            value={
                "id": 2,
                "nickname": "산악인",
                "bio": "산이 좋아요",
                "profile_img_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/profiles/2_avatar.jpg",
                "tags": [
                    {"id": 11, "name": "산·숲·계곡"},
                    {"id": 13, "name": "자연공원·트레킹"},
                ],
                "follower_count": 4,
                "following_count": 6,
                "travel_type_name": "모험가형",
                "is_following": False,
            },
            response_only=True,
        ),
    ],
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
    examples=[
        OpenApiExample(
            "공개 리뷰 목록 응답",
            value={
                "count": 3,
                "next": "http://localhost:8000/api/v1/users/2/reviews?page=2",
                "previous": None,
                "results": [
                    {
                        "review_id": 1,
                        "place_id": 1,
                        "place_name": "부산 광안리 해수욕장",
                        "rating": 5,
                        "content": "야경이 정말 예뻐요!",
                        "created_at": "2026-05-22T12:23:11Z",
                        "updated_at": "2026-05-22T12:23:11Z",
                    },
                ],
            },
            response_only=True,
        ),
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
    examples=[
        OpenApiExample(
            "사용 가능 응답",
            value={"detail": "사용가능한 닉네임 입니다."},
            response_only=True,
        ),
    ],
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
        "프로필 이미지를 S3에 직접 업로드할 수 있는 presigned URL을 발급합니다.\n"
        "응답으로 받은 img_url을 `PATCH /api/v1/users` 요청의 profile_image_url 필드에 담아 전달하세요."
    ),
    request=PresignedUrlRequestSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={"file_name": "avatar.jpg"},
            request_only=True,
        ),
        OpenApiExample(
            "presigned URL 발급 응답",
            value={
                "presigned_url": "https://travel-maker-bucket.s3.amazonaws.com/profiles/uuid_avatar.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
                "img_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/profiles/uuid_avatar.jpg",
                "key": "profiles/uuid_avatar.jpg",
                "content_type": "image/jpeg",
            },
            response_only=True,
        ),
    ],
    responses={
        200: PresignedUrlResponseSerializer,
        400: OpenApiResponse(description="지원하지 않는 파일 형식입니다."),
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
        503: OpenApiResponse(description="이미지 업로드 URL 발급에 실패했습니다."),
    },
)
