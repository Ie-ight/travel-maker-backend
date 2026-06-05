from django.contrib import admin

from apps.core.admin import BaseAdmin
from apps.place.models import Place, PlaceFeature, PlaceImage, PlaceInfo, Tag


class PlaceImageInline(admin.TabularInline):  # type: ignore[type-arg]
    model = PlaceImage
    extra = 1


@admin.register(Place)
class PlaceAdmin(BaseAdmin):
    list_display = ["id", "place_name", "rating_avg", "rating_count", "created_at"]
    list_display_links = ["id", "place_name"]
    search_fields = ["place_name"]
    filter_horizontal = ["tags"]
    inlines = [PlaceImageInline]
    list_select_related = True


@admin.register(Tag)
class TagAdmin(BaseAdmin):
    list_display = ["id", "tag_name", "tag_type"]
    list_display_links = ["id", "tag_name"]
    list_filter = ["tag_type"]
    search_fields = ["tag_name"]
    list_per_page = 50  # 태그는 많으므로 오버라이드


@admin.register(PlaceInfo)
class PlaceInfoAdmin(BaseAdmin):
    list_display = ["id", "place", "parking", "pet", "baby_carriage", "credit_card"]
    list_display_links = ["id", "place"]
    search_fields = ["place__place_name"]
    list_select_related = ["place"]


@admin.register(PlaceFeature)
class PlaceFeatureAdmin(BaseAdmin):
    list_display = ["id", "place", "updated_at"]
    list_display_links = ["id", "place"]
    search_fields = ["place__place_name"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["place"]
