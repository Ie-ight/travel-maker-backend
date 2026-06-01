from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookmark.schemas import bookmark_create_schema, bookmark_delete_schema, bookmark_list_schema
from apps.bookmark.serializers import BookmarkCreateSerializer, BookmarkSerializer
from apps.bookmark.services import BookmarkService


class BookmarkListView(APIView):
    permission_classes = [IsAuthenticated]

    @bookmark_list_schema
    def get(self, request: Request) -> Response:
        """내 북마크 목록 조회"""
        bookmarks = BookmarkService.get_bookmarks(request.user)
        serializer = BookmarkSerializer(bookmarks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BookmarkCreateDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @bookmark_create_schema
    def post(self, request: Request, place_id: int) -> Response:
        """북마크 추가"""
        serializer = BookmarkCreateSerializer(
            data={"place": place_id},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        bookmark = BookmarkService.create_bookmark(request.user, place_id)
        return Response(
            {"message": "북마크가 추가되었습니다.", "bookmark_id": bookmark.id},
            status=status.HTTP_201_CREATED,
        )

    @bookmark_delete_schema
    def delete(self, request: Request, place_id: int) -> Response:
        """북마크 삭제"""
        BookmarkService.delete_bookmark(request.user, place_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
