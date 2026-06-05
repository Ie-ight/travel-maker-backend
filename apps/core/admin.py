from django.contrib import admin


class BaseAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_per_page = 20
    show_full_result_count = False
    ordering = ["-id"]
