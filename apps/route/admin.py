from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from apps.core.admin import BaseAdmin, SmallTextFieldMixIn
from apps.route.models import Route, RouteDay, RouteDayPlace, RouteLike


class RouteDayPlaceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = RouteDayPlace
    extra = 0
    fields = ["order", "place"]
    autocomplete_fields = ["place"]
    ordering = ["order"]


@admin.register(RouteDay)
class RouteDayAdmin(BaseAdmin):
    list_display = ["id", "route", "day_index", "places_count"]
    list_display_links = ["id", "route"]
    list_select_related = ["route"]
    autocomplete_fields = ["route"]
    inlines = [RouteDayPlaceInline]
    search_fields = ["route__title"]

    def get_model_perms(self, request: HttpRequest) -> dict[str, bool]:
        # 사이드바 목록(인덱스)에서는 숨기되, 인라인의 '변경' 버튼을 통해서만 접근하도록 합니다.
        return {}

    @admin.display(description="장소 수")
    def places_count(self, obj: RouteDay) -> int:
        return obj.day_places.count()


class RouteDayInline(admin.TabularInline):  # type: ignore[type-arg]
    """RouteAdmin 내에서 일차(1일차, 2일차...) 목록과 포함된 장소들을 간략히 보여줍니다."""

    model = RouteDay
    extra = 0
    fields = ["day_index", "places_summary", "edit_button"]
    readonly_fields = ["places_summary", "edit_button"]
    ordering = ["day_index"]
    show_change_link = False  # 기본 제공되는 작은 연필 아이콘은 숨김

    @admin.display(description="장소 관리")
    def edit_button(self, obj: RouteDay) -> str:
        if not obj.pk:
            return "저장 후 관리 가능"
        from django.urls import reverse
        from django.utils.html import format_html

        url = reverse("admin:route_routeday_change", args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" style="padding: 6px 12px; font-size: 12px; font-weight: bold; background-color: #417690; color: white; border-radius: 4px; text-decoration: none; display: inline-block;">'
            "장소 추가/수정 📝"
            "</a>",
            url,
        )

    @admin.display(description="포함된 장소들")
    def places_summary(self, obj: RouteDay) -> str:
        if not obj.pk:
            return "—"
        places = obj.day_places.select_related("place").order_by("order")
        if not places:
            return "장소 없음"
        return format_html("<br>".join(f"{p.order}. <b>{p.place.place_name}</b>" for p in places))


@admin.register(Route)
class RouteAdmin(SmallTextFieldMixIn, BaseAdmin):
    list_display = ["id", "user", "title", "region_tag", "start_date", "end_date", "like_count", "created_at"]
    list_display_links = ["id", "title"]
    list_filter = ["start_date"]
    search_fields = ["title", "user__nickname"]
    readonly_fields = ["like_count", "created_at", "updated_at"]
    list_select_related = ["user", "region_tag"]
    autocomplete_fields = ["user", "region_tag"]
    filter_horizontal = ["theme_tags"]
    save_on_top = True
    inlines = [RouteDayInline]
    fieldsets = [
        (None, {"fields": ["user", "title", "description", "like_count", "end_date", "region_tag", "theme_tags"]}),
        ("메타", {"classes": ["collapse"], "fields": ["created_at", "updated_at"]}),
    ]

    def formfield_for_foreignkey(self, db_field: Any, request: Any, **kwargs: Any) -> Any:  # type: ignore
        if db_field.name == "region_tag":
            from apps.place.models import Tag

            kwargs["queryset"] = Tag.objects.filter(tag_type=Tag.TagType.REGION)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field: Any, request: Any, **kwargs: Any) -> Any:  # type: ignore
        if db_field.name == "theme_tags":
            from apps.place.models import Tag

            kwargs["queryset"] = Tag.objects.exclude(tag_type=Tag.TagType.REGION)
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(RouteLike)
class RouteLikeAdmin(BaseAdmin):
    list_display = ["id", "user", "route", "created_at"]
    list_display_links = ["id"]
    search_fields = ["user__nickname", "route__title"]
    list_select_related = ["user", "route"]
    autocomplete_fields = ["user", "route"]
    readonly_fields = ["created_at"]

    def get_model_perms(self, request: HttpRequest) -> dict[str, bool]:
        # 유저 상세의 인라인에서 주로 관리하므로 메인 메뉴에서는 숨김
        return {}
