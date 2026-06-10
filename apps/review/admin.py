from django.contrib import admin
from django.utils.safestring import SafeString

from apps.core.admin import BaseAdmin, render_thumbnail
from apps.review.models import Review


@admin.register(Review)
class ReviewAdmin(BaseAdmin):
    list_display = ["id", "user", "place", "rating", "content_preview", "image_thumb", "created_at"]
    list_display_links = ["id"]
    list_filter = ["rating", "created_at"]
    search_fields = ["user__nickname", "place__place_name", "content"]
    autocomplete_fields = ["user", "place"]
    readonly_fields = ["image_preview", "created_at", "updated_at"]
    date_hierarchy = "created_at"
    list_select_related = ["user", "place"]

    @admin.display(description="내용")
    def content_preview(self, obj: Review) -> str:
        text = obj.content or ""
        return text[:30] + ("…" if len(text) > 30 else "")

    @admin.display(description="이미지")
    def image_thumb(self, obj: Review) -> SafeString | str:
        return render_thumbnail(obj.image_url, size=48)

    @admin.display(description="이미지 미리보기")
    def image_preview(self, obj: Review) -> SafeString | str:
        return render_thumbnail(obj.image_url, size=200)
