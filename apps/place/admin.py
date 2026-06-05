from django.contrib import admin

from apps.place.models import Place, PlaceFeature, PlaceImage, PlaceInfo, Tag


class PlaceImageInline(admin.TabularInline):  # type: ignore[type-arg]
    model = PlaceImage
    extra = 1


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "place_name", "rating_avg", "rating_count", "created_at"]
    list_display_links = ["id", "place_name"]
    search_fields = ["place_name"]
    filter_horizontal = ["tags"]
    inlines = [PlaceImageInline]
    ordering = ["-id"]
    list_per_page = 20
    show_full_result_count = False
    list_select_related = True


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "tag_name", "tag_type"]
    list_display_links = ["id", "tag_name"]
    list_filter = ["tag_type"]
    search_fields = ["tag_name"]
    list_per_page = 50
    show_full_result_count = False


@admin.register(PlaceInfo)
class PlaceInfoAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "place", "parking", "pet", "baby_carriage", "credit_card"]
    list_display_links = ["id", "place"]
    search_fields = ["place__place_name"]
    ordering = ["-id"]
    list_per_page = 20
    show_full_result_count = False
    list_select_related = ["place"]


@admin.register(PlaceFeature)
class PlaceFeatureAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "place", "updated_at"]
    list_display_links = ["id", "place"]
    search_fields = ["place__place_name"]
    ordering = ["-id"]
    readonly_fields = ["created_at", "updated_at"]
    list_per_page = 20
    show_full_result_count = False
    list_select_related = ["place"]
