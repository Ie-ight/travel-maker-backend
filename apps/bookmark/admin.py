from django.contrib import admin

from apps.bookmark.models import Bookmark


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "user", "place", "created_at"]
    list_display_links = ["id"]
    search_fields = ["user__nickname", "place__place_name"]
    ordering = ["-id"]
    readonly_fields = ["created_at"]
    list_per_page = 20
    show_full_result_count = False
    list_select_related = ["user", "place"]
