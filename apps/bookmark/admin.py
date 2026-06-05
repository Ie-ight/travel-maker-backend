from django.contrib import admin

from apps.bookmark.models import Bookmark
from apps.core.admin import BaseAdmin


@admin.register(Bookmark)
class BookmarkAdmin(BaseAdmin):
    list_display = ["id", "user", "place", "created_at"]
    list_display_links = ["id"]
    search_fields = ["user__nickname", "place__place_name"]
    readonly_fields = ["created_at"]
    list_select_related = ["user", "place"]
