from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookmark.serializers import BookmarkCreateSerializer, BookmarkSerializer
from apps.bookmark.services import BookmarkService


class BookmarkListCreateView(APIView):  # type: ignore[misc]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """내 북마크 목록 조회"""
        bookmarks = BookmarkService.get_bookmarks(request.user)
        serializer = BookmarkSerializer(bookmarks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        """북마크 추가"""
        serializer = BookmarkCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        bookmark = BookmarkService.create_bookmark(
            user=request.user,
            place_id=serializer.validated_data["place"].id,
        )
        result = BookmarkSerializer(bookmark)
        return Response(result.data, status=status.HTTP_201_CREATED)


class BookmarkDeleteView(APIView):  # type: ignore[misc]
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, place_id: int) -> Response:
        """북마크 삭제"""
        BookmarkService.delete_bookmark(request.user, place_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
