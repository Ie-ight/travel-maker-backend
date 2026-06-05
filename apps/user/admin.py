from django.contrib import admin

from apps.user.models import Follow, SocialUser, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "nickname", "email", "is_active", "role", "created_at"]
    list_display_links = ["id", "nickname"]
    list_filter = ["is_active", "role"]
    search_fields = ["nickname", "email"]
    ordering = ["-id"]
    readonly_fields = ["created_at", "updated_at", "last_login"]
    exclude = ["password"]
    list_per_page = 20
    show_full_result_count = False


@admin.register(SocialUser)
class SocialUserAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "user", "provider", "provider_id", "created_at"]
    list_display_links = ["id"]
    list_filter = ["provider"]
    search_fields = ["user__nickname", "provider_id"]
    ordering = ["-id"]
    readonly_fields = ["created_at", "updated_at"]
    list_per_page = 20
    show_full_result_count = False
    list_select_related = ["user"]


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "follower", "following", "created_at"]
    list_display_links = ["id"]
    search_fields = ["follower__nickname", "following__nickname"]
    ordering = ["-id"]
    readonly_fields = ["created_at"]
    list_per_page = 20
    show_full_result_count = False
    list_select_related = ["follower", "following"]
