from typing import Any

from django import forms
from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from apps.bookmark.models import Bookmark
from apps.core.admin import BaseAdmin, apply_vector_widget, format_style_vector
from apps.travel_quiz.models import UserTestResult
from apps.user.models import Follow, SocialUser, User


class SocialUserInline(admin.TabularInline):  # type: ignore[type-arg]
    model = SocialUser
    extra = 0
    fields = ["provider", "provider_id", "created_at"]
    readonly_fields = ["created_at"]
    classes = ["collapse"]


class UserTestResultInline(admin.StackedInline):  # type: ignore[type-arg]
    model = UserTestResult
    extra = 0
    can_delete = True
    autocomplete_fields = ["travel_type"]
    fields = ["travel_type", "result_vector", "vector_readable", "updated_at"]
    readonly_fields = ["vector_readable", "updated_at"]
    classes = ["collapse"]

    def formfield_for_dbfield(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> forms.Field | None:
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        return apply_vector_widget(formfield, db_field.name, "result_vector")

    @admin.display(description="현재 값(라벨)")
    def vector_readable(self, obj: UserTestResult) -> str:
        return format_style_vector(obj.result_vector)


class FollowingInline(admin.TabularInline):  # type: ignore[type-arg]
    """이 유저가 팔로우하는 사람(팔로잉). Follow.follower = 이 유저."""

    model = Follow
    fk_name = "follower"
    extra = 0
    fields = ["following", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["following"]
    classes = ["collapse"]
    verbose_name = "팔로잉"
    verbose_name_plural = "팔로잉 (이 유저가 팔로우하는 사람)"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Follow]:
        qs: QuerySet[Follow] = super().get_queryset(request)
        return qs.select_related("following")


class FollowerInline(admin.TabularInline):  # type: ignore[type-arg]
    """이 유저를 팔로우하는 사람(팔로워). Follow.following = 이 유저."""

    model = Follow
    fk_name = "following"
    extra = 0
    fields = ["follower", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["follower"]
    classes = ["collapse"]
    verbose_name = "팔로워"
    verbose_name_plural = "팔로워 (이 유저를 팔로우하는 사람)"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Follow]:
        qs: QuerySet[Follow] = super().get_queryset(request)
        return qs.select_related("follower")


class BookmarkInline(admin.TabularInline):  # type: ignore[type-arg]
    """이 유저가 북마크한 장소."""

    model = Bookmark
    extra = 0
    fields = ["place", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["place"]
    classes = ["collapse"]
    verbose_name = "북마크"
    verbose_name_plural = "북마크 (이 유저가 저장한 장소)"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Bookmark]:
        qs: QuerySet[Bookmark] = super().get_queryset(request)
        return qs.select_related("place")


@admin.register(User)
class UserAdmin(BaseAdmin):
    list_display = [
        "id",
        "nickname",
        "email",
        "role",
        "is_active",
        "tags_display",
        "review_count",
        "bookmark_count",
        "follower_count",
        "following_count",
        "created_at",
    ]
    list_display_links = ["id", "nickname"]
    list_filter = ["is_active", "role", "gender", "tags"]
    search_fields = ["nickname", "email"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "updated_at", "last_login"]
    exclude = ["password"]
    filter_horizontal = ["tags"]
    inlines = [SocialUserInline, UserTestResultInline, FollowingInline, FollowerInline, BookmarkInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:
        qs: QuerySet[User] = super().get_queryset(request)
        return qs.prefetch_related("tags").annotate(
            review_count=Count("reviews", distinct=True),
            bookmark_count=Count("bookmarks", distinct=True),
            # Follow.follower related_name="followers"(이 유저의 팔로잉), following related_name="followings"(이 유저의 팔로워)
            following_count=Count("followers", distinct=True),
            follower_count=Count("followings", distinct=True),
        )

    @admin.display(description="관심 태그")
    def tags_display(self, obj: User) -> str:
        tags = list(obj.tags.all())  # get_queryset에서 prefetch됨
        return ", ".join(tag.tag_name for tag in tags) if tags else "—"

    @admin.display(description="리뷰수", ordering="review_count")
    def review_count(self, obj: User) -> int:
        return int(getattr(obj, "review_count", 0) or 0)

    @admin.display(description="북마크수", ordering="bookmark_count")
    def bookmark_count(self, obj: User) -> int:
        return int(getattr(obj, "bookmark_count", 0) or 0)

    @admin.display(description="팔로워수", ordering="follower_count")
    def follower_count(self, obj: User) -> int:
        return int(getattr(obj, "follower_count", 0) or 0)

    @admin.display(description="팔로잉수", ordering="following_count")
    def following_count(self, obj: User) -> int:
        return int(getattr(obj, "following_count", 0) or 0)


# SocialUser·Follow는 User 상세 인라인에서 보고 편집하므로 독립 admin(메뉴 항목)은 두지 않는다.
