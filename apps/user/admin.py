from django.contrib import admin

from apps.user.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["id", "nickname", "email", "is_active", "role", "created_at"]
    list_filter = ["is_active", "role"]
    search_fields = ["nickname", "email"]
    ordering = ["-created_at"]
