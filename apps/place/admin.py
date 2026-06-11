from typing import Any

from django import forms
from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.utils.safestring import SafeString

from apps.bookmark.models import Bookmark
from apps.core.admin import BaseAdmin, apply_vector_widget, format_style_vector, render_thumbnail
from apps.place.models import Place, PlaceFeature, PlaceImage, PlaceInfo, Tag
from apps.review.models import Review


class PlaceImageInline(admin.TabularInline):  # type: ignore[type-arg]
    model = PlaceImage
    extra = 1
    fields = ["thumb", "image_url", "thumbnail_url", "is_main", "order"]
    readonly_fields = ["thumb"]

    @admin.display(description="미리보기")
    def thumb(self, obj: PlaceImage) -> SafeString | str:
        return render_thumbnail(obj.thumbnail_url or obj.image_url, size=60)


class PlaceInfoInline(admin.StackedInline):  # type: ignore[type-arg]
    model = PlaceInfo
    extra = 0
    can_delete = True


class PlaceFeatureInline(admin.StackedInline):  # type: ignore[type-arg]
    model = PlaceFeature
    extra = 0
    can_delete = True
    fields = ["style_vector", "style_vector_readable", "updated_at"]
    readonly_fields = ["style_vector_readable", "updated_at"]

    def formfield_for_dbfield(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> forms.Field | None:
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        return apply_vector_widget(formfield, db_field.name, "style_vector")

    @admin.display(description="현재 값(라벨)")
    def style_vector_readable(self, obj: PlaceFeature) -> str:
        return format_style_vector(obj.style_vector)


class ReviewInline(admin.TabularInline):  # type: ignore[type-arg]
    model = Review
    extra = 0
    fields = ["user", "rating", "content", "image_url", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["user"]
    show_change_link = True


class BookmarkInline(admin.TabularInline):  # type: ignore[type-arg]
    """이 장소를 북마크한 유저."""

    model = Bookmark
    extra = 0
    fields = ["user", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["user"]
    verbose_name = "북마크"
    verbose_name_plural = "북마크 (이 장소를 저장한 유저)"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Bookmark]:
        qs: QuerySet[Bookmark] = super().get_queryset(request)
        return qs.select_related("user")


@admin.register(Place)
class PlaceAdmin(BaseAdmin):
    list_display = [
        "id",
        "main_thumb",
        "place_name",
        "address_primary",
        "rating_avg",
        "rating_count",
        "review_count",
        "bookmark_count",
        "is_active",
        "created_at",
    ]
    list_display_links = ["id", "place_name"]
    list_editable = ["is_active"]
    list_filter = ["is_active", "content_type_id", "lcls_systm1"]
    search_fields = ["place_name", "address_primary"]
    date_hierarchy = "created_at"
    filter_horizontal = ["tags"]
    inlines = [PlaceImageInline, PlaceInfoInline, PlaceFeatureInline, ReviewInline, BookmarkInline]
    readonly_fields = ["rating_avg", "rating_count", "created_at", "updated_at"]
    save_on_top = True
    actions = ["activate", "deactivate"]
    fieldsets = [
        # 기본 섹션만 펼쳐두고, 나머지는 접어서 스크롤을 줄인다.
        (None, {"fields": ["place_name", "description", "is_active", "tags"]}),
        ("평점", {"fields": ["rating_avg", "rating_count"]}),
        (
            "위치",
            {
                "fields": ["address_primary", "address_detail", "zipcode", "latitude", "longitude"],
            },
        ),
        ("연락처", {"fields": ["tel", "homepage"]}),
        (
            "분류 · Tour API",
            {
                "fields": [
                    "content_id",
                    "content_type_id",
                    "lcls_systm1",
                    "lcls_systm2",
                    "lcls_systm3",
                    "source_modified_at",
                ],
            },
        ),
        ("메타", {"fields": ["created_at", "updated_at"]}),
    ]

    @admin.action(description="선택한 장소 활성화")
    def activate(self, request: HttpRequest, queryset: QuerySet[Place]) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated}개 장소를 활성화했습니다.")

    @admin.action(description="선택한 장소 비활성화")
    def deactivate(self, request: HttpRequest, queryset: QuerySet[Place]) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated}개 장소를 비활성화했습니다.")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Place]:
        qs: QuerySet[Place] = super().get_queryset(request)
        return qs.prefetch_related("images").annotate(
            review_count=Count("reviews", distinct=True),
            bookmark_count=Count("bookmarks", distinct=True),
        )

    @admin.display(description="대표")
    def main_thumb(self, obj: Place) -> SafeString | str:
        images = list(obj.images.all())  # get_queryset에서 prefetch됨
        if not images:
            return ""
        main = next((img for img in images if img.is_main), images[0])
        return render_thumbnail(main.thumbnail_url or main.image_url, size=48)

    @admin.display(description="리뷰수", ordering="review_count")
    def review_count(self, obj: Place) -> int:
        return int(getattr(obj, "review_count", 0) or 0)

    @admin.display(description="북마크수", ordering="bookmark_count")
    def bookmark_count(self, obj: Place) -> int:
        return int(getattr(obj, "bookmark_count", 0) or 0)


@admin.register(Tag)
class TagAdmin(BaseAdmin):
    list_display = ["id", "tag_name", "tag_type"]
    list_display_links = ["id", "tag_name"]
    list_filter = ["tag_type"]
    search_fields = ["tag_name"]
    list_per_page = 50  # 태그는 많으므로 오버라이드


# PlaceInfo·PlaceFeature는 Place 상세 인라인에서 보고 편집하므로 독립 admin(메뉴 항목)은 두지 않는다.
