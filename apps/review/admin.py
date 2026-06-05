from django.contrib import admin

from apps.core.admin import BaseAdmin
from apps.review.models import Review


@admin.register(Review)
class ReviewAdmin(BaseAdmin):
    list_display = ["id", "user", "place", "rating", "created_at"]
    list_display_links = ["id"]
    list_filter = ["rating"]
    search_fields = ["user__nickname", "place__place_name", "content"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["user", "place"]
