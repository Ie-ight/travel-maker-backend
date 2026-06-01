from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.bookmark.serializers import BookmarkCreateResponseSerializer, BookmarkSerializer

bookmark_list_schema = extend_schema(
    tags=["Bookmark"],
    summary="북마크 목록 조회",
    description="로그인한 유저의 북마크 목록을 조회합니다.",
    responses={
        200: BookmarkSerializer,
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
    },
)

bookmark_create_schema = extend_schema(
    tags=["Bookmark"],
    summary="북마크 등록",
    description="여행지를 북마크에 추가합니다. 비회원 접근 불가. 이미 북마크 시 409.",
    responses={
        201: BookmarkCreateResponseSerializer,
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
        404: OpenApiResponse(description="존재하지 않는 장소입니다."),
        409: OpenApiResponse(description="이미 북마크된 장소입니다."),
    },
)

bookmark_delete_schema = extend_schema(
    tags=["Bookmark"],
    summary="북마크 해제",
    description="북마크를 해제합니다. 북마크 내역 없으면 404.",
    responses={
        204: OpenApiResponse(description="북마크가 해제되었습니다."),
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
        404: OpenApiResponse(description="북마크 내역을 찾을 수 없습니다."),
    },
)
