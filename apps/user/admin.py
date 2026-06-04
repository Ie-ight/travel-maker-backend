from django.contrib import admin

from apps.user.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "nickname", "email", "is_active", "role", "created_at"]
    list_display_links = ["id", "nickname"]
    list_filter = ["is_active", "role"]
    search_fields = ["nickname", "email"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at", "last_login"]  # 읽기 전용
    exclude = ["password"]  # 비밀번호 숨기기
