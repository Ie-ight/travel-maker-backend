from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from apps.bookmark.models import Bookmark
from apps.place.models import Place


class BookmarkService:
    @staticmethod
    def get_bookmarks(user: Any) -> QuerySet[Bookmark]:
        qs: QuerySet[Bookmark] = Bookmark.objects.filter(user=user)  # type: ignore[attr-defined]
        return qs.select_related("place").prefetch_related("place__images").order_by("-created_at")

    @staticmethod
    def create_bookmark(user: Any, place_id: int) -> Bookmark:
        place = get_object_or_404(Place, id=place_id)
        return Bookmark.objects.create(user=user, place=place)

    @staticmethod
    def delete_bookmark(user: Any, place_id: int) -> None:
        bookmark = get_object_or_404(Bookmark, user=user, place_id=place_id)
        bookmark.delete()
