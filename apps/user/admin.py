from django.contrib import admin

from apps.core.admin import BaseAdmin
from apps.user.models import Follow, SocialUser, User


@admin.register(User)
class UserAdmin(BaseAdmin):
    list_display = ["id", "nickname", "email", "is_active", "role", "created_at"]
    list_display_links = ["id", "nickname"]
    list_filter = ["is_active", "role"]
    search_fields = ["nickname", "email"]
    readonly_fields = ["created_at", "updated_at", "last_login"]
    exclude = ["password"]


@admin.register(SocialUser)
class SocialUserAdmin(BaseAdmin):
    list_display = ["id", "user", "provider", "provider_id", "created_at"]
    list_display_links = ["id"]
    list_filter = ["provider"]
    search_fields = ["user__nickname", "provider_id"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["user"]


@admin.register(Follow)
class FollowAdmin(BaseAdmin):
    list_display = ["id", "follower", "following", "created_at"]
    list_display_links = ["id"]
    search_fields = ["follower__nickname", "following__nickname"]
    readonly_fields = ["created_at"]
    list_select_related = ["follower", "following"]
