import re
from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.utils import validate_s3_image_url
from apps.user.models import Follow, User


class _UserTagSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """프로필 응답의 tags 항목 스키마 문서용 (id, name)"""

    id = serializers.IntegerField()
    name = serializers.CharField()


class _UserProfileFieldsMixin:
    """ProfileSerializer / PublicUserSerializer가 공유하는 필드 계산 로직."""

    def get_follower_count(self, obj: User) -> int:
        # Follow.following == obj 인 행 = obj를 팔로우하는 사람들 = obj의 팔로워
        return obj.followings.count()

    def get_following_count(self, obj: User) -> int:
        # Follow.follower == obj 인 행 = obj가 팔로우하는 사람들 = obj의 팔로잉
        return obj.followers.count()

    @extend_schema_field(_UserTagSerializer(many=True))
    def get_tags(self, obj: User) -> list[dict[str, Any]]:
        return [{"id": tag.id, "name": tag.tag_name} for tag in obj.tags.all()]

    def get_travel_type_name(self, obj: User) -> str | None:
        result = getattr(obj, "usertestresult", None)
        return result.travel_type.name if result else None


class ProfileSerializer(_UserProfileFieldsMixin, serializers.ModelSerializer[User]):
    """프로필 조회 응답"""

    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    bookmark_count = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    travel_type_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "nickname",
            "bio",
            "email",
            "profile_img_url",
            "tags",
            "follower_count",
            "following_count",
            "bookmark_count",
            "review_count",
            "travel_type_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_bookmark_count(self, obj: User) -> int:
        return obj.bookmarks.count()

    def get_review_count(self, obj: User) -> int:
        return obj.reviews.count()


class ProfileUpdateSerializer(serializers.ModelSerializer[User]):
    """프로필 수정 요청"""

    profile_image_url = serializers.URLField(required=False)

    class Meta:
        model = User
        fields = [
            "nickname",
            "bio",
            "profile_image_url",
            "tags",
        ]

    def validate_nickname(self, value: str) -> str:
        if not re.match(r"^[a-z가-힣]+$", value):
            raise serializers.ValidationError("닉네임은 영소문자와 한글만 허용됩니다.")
        return value

    def validate_profile_image_url(self, value: str) -> str:
        return validate_s3_image_url(value)


class ProfileUpdateResponseSerializer(_UserProfileFieldsMixin, serializers.ModelSerializer[User]):
    """프로필 수정 응답"""

    tags = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "nickname",
            "bio",
            "profile_img_url",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PublicUserSerializer(_UserProfileFieldsMixin, serializers.ModelSerializer[User]):
    """공개 프로필 조회 응답 (email, bookmark_count, review_count 미포함)"""

    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    travel_type_name = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    def get_is_following(self, obj: User) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return Follow.objects.filter(follower=request.user, following=obj).exists()

    class Meta:
        model = User
        fields = [
            "id",
            "nickname",
            "bio",
            "profile_img_url",
            "tags",
            "follower_count",
            "following_count",
            "travel_type_name",
            "is_following",
        ]
        read_only_fields = fields


class NicknameCheckSerializer(serializers.Serializer):  # type: ignore[type-arg]
    nickname = serializers.CharField(required=True)


class NicknameCheckResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    detail = serializers.CharField()


class UserBookmarkSerializer(serializers.ModelSerializer[Any]):
    """내 북마크 목록 응답"""

    place_id = serializers.IntegerField(source="place.id")
    place_name = serializers.CharField(source="place.place_name")
    description = serializers.CharField(source="place.description")
    image_url = serializers.SerializerMethodField()
    rating = serializers.FloatField(source="place.rating_avg")

    class Meta:
        from apps.bookmark.models import Bookmark

        model = Bookmark
        fields = [
            "place_id",
            "place_name",
            "description",
            "image_url",
            "rating",
            "created_at",
        ]
        read_only_fields = fields

    def get_image_url(self, obj: Any) -> str | None:
        image = obj.place.images.filter(is_main=True).first()
        return image.image_url if image else None


class UserReviewSerializer(serializers.ModelSerializer[Any]):
    """내 리뷰 목록 응답"""

    review_id = serializers.IntegerField(source="id")
    place_id = serializers.IntegerField(source="place.id")
    place_name = serializers.CharField(source="place.place_name")

    class Meta:
        from apps.review.models import Review

        model = Review
        fields = [
            "review_id",
            "place_id",
            "place_name",
            "rating",
            "content",
            "image_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
