from django.contrib import admin

from apps.place.models import Place


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("place_name", "rating_avg")
    search_fields = ["place_name"]
