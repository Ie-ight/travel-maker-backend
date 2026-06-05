from django.contrib import admin

from apps.review.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "user", "place", "rating", "created_at"]
    list_display_links = ["id"]
    list_filter = ["rating"]
    search_fields = ["user__nickname", "place__place_name", "content"]
    ordering = ["-id"]
    readonly_fields = ["created_at", "updated_at"]
    list_per_page = 20
    show_full_result_count = False
    list_select_related = ["user", "place"]
