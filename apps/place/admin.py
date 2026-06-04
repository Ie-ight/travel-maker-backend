from django.contrib import admin

from apps.place.models import Place, PlaceImage, Tag


class PlaceImageInline(admin.TabularInline):  # type: ignore[type-arg]
    model = PlaceImage
    extra = 1


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "place_name", "rating_avg", "rating_count", "created_at"]
    search_fields = ["place_name"]
    filter_horizontal = ["tags"]
    inlines = [PlaceImageInline]
    ordering = ["-created_at"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "tag_name", "tag_type"]
    list_filter = ["tag_type"]
    search_fields = ["tag_name"]
