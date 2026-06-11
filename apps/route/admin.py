from django.contrib import admin

from apps.core.admin import BaseAdmin
from apps.route.models import Route, RouteDayPlace, RouteLike


class RouteDayPlaceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = RouteDayPlace
    extra = 0


@admin.register(Route)
class RouteAdmin(BaseAdmin):
    list_display = ["id", "user", "title", "start_date", "end_date", "like_count", "created_at"]
    list_display_links = ["id", "title"]
    list_filter = ["start_date"]
    search_fields = ["title", "user__nickname"]
    readonly_fields = ["like_count", "created_at", "updated_at"]
    list_select_related = ["user"]
    filter_horizontal = ["theme_tags"]


@admin.register(RouteLike)
class RouteLikeAdmin(BaseAdmin):
    list_display = ["id", "user", "route", "created_at"]
    list_display_links = ["id"]
    search_fields = ["user__nickname", "route__title"]
    list_select_related = ["user", "route"]
