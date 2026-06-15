from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from apps.bookmark.models import Bookmark
from apps.place.models import Place
from apps.user.models import UserActionLog
from apps.user.services.action_log_service import record_action


class BookmarkService:
    @staticmethod
    def get_bookmarks(user: Any) -> QuerySet[Bookmark]:
        qs: QuerySet[Bookmark] = Bookmark.objects.filter(user=user)  # type: ignore[attr-defined]
        return qs.select_related("place").prefetch_related("place__images").order_by("-created_at")

    @staticmethod
    @transaction.atomic
    def create_bookmark(user: Any, place_id: int) -> Bookmark:
        place = get_object_or_404(Place, id=place_id)
        bookmark = Bookmark.objects.create(user=user, place=place)
        record_action(user, place, UserActionLog.ActionType.BOOKMARK)
        return bookmark

    @staticmethod
    @transaction.atomic
    def delete_bookmark(user: Any, place_id: int) -> None:
        bookmark = get_object_or_404(Bookmark, user=user, place_id=place_id)
        place = bookmark.place
        bookmark.delete()
        record_action(user, place, UserActionLog.ActionType.UNBOOKMARK)
