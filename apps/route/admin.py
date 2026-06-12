from django.contrib import admin

from apps.core.admin import BaseAdmin
from apps.route.models import Route, RouteDayPlace, RouteLike


class RouteDayPlaceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = RouteDayPlace
    extra = 0
    classes = ["collapse"]
    fields = ["place", "order"]
    autocomplete_fields = ["place"]


@admin.register(Route)
class RouteAdmin(BaseAdmin):
    list_display = ["id", "user", "title", "region_tag", "start_date", "end_date", "like_count", "created_at"]
    list_display_links = ["id", "title"]
    list_filter = ["start_date"]
    search_fields = ["title", "user__nickname"]
    readonly_fields = ["like_count", "created_at", "updated_at"]
    list_select_related = ["user", "region_tag"]
    autocomplete_fields = ["user", "region_tag", "theme_tags"]
    save_on_top = True
    fieldsets = [
        (None, {"fields": ["user", "title", "description"]}),
        ("태그", {"classes": ["collapse"], "fields": ["region_tag", "theme_tags"]}),
        ("일정", {"classes": ["collapse"], "fields": ["start_date", "end_date"]}),
        ("통계", {"classes": ["collapse"], "fields": ["like_count"]}),
        ("메타", {"classes": ["collapse"], "fields": ["created_at", "updated_at"]}),
    ]


@admin.register(RouteLike)
class RouteLikeAdmin(BaseAdmin):
    list_display = ["id", "user", "route", "created_at"]
    list_display_links = ["id"]
    search_fields = ["user__nickname", "route__title"]
    list_select_related = ["user", "route"]
    autocomplete_fields = ["user", "route"]
    readonly_fields = ["created_at"]
