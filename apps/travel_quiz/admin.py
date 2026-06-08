from django.contrib import admin

from apps.core.admin import BaseAdmin
from apps.travel_quiz.models import TravelType, UserTestResult


@admin.register(TravelType)
class TravelTypeAdmin(BaseAdmin):
    list_display = ["id", "type_key", "name", "description"]
    list_display_links = ["id", "type_key"]
    search_fields = ["type_key", "name"]
    list_filter = ["tags"]
    filter_horizontal = ["tags"]


@admin.register(UserTestResult)
class UserTestResultAdmin(BaseAdmin):
    list_display = ["id", "user", "travel_type", "updated_at"]
    list_display_links = ["id"]
    search_fields = ["user__nickname", "travel_type__type_key"]
    list_filter = ["travel_type", "updated_at"]
    readonly_fields = ["result_vector", "updated_at"]
    list_select_related = ["user", "travel_type"]
