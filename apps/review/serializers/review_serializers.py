from rest_framework import serializers

from apps.core.utils import validate_s3_image_url
from apps.review.models import Review
from apps.route.models import Route


# 응답에 본인 작성 여부(is_owner)를 추가하는 믹스인
class IsOwnerMixin(serializers.Serializer[Review]):
    is_owner = serializers.SerializerMethodField()

    def get_is_owner(self, obj: Review) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return bool(obj.user_id == request.user.id)
        return False


# 리뷰에 연결된 경로 응답
class ReviewRouteSerializer(serializers.ModelSerializer[Route]):
    route_id = serializers.IntegerField(source="id")

    class Meta:
        model = Route
        fields = ["route_id", "title"]
        read_only_fields = fields


# 리뷰 목록 응답(닉네임 포함)
class ReviewListItemSerializer(IsOwnerMixin, serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")
    user_nickname = serializers.CharField(source="user.nickname")
    user_profile_img_url = serializers.SerializerMethodField()
    route = ReviewRouteSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            "review_id",
            "user_id",
            "user_nickname",
            "user_profile_img_url",
            "rating",
            "content",
            "image_url",
            "created_at",
            "updated_at",
            "is_owner",
            "route",
        ]

    def get_user_profile_img_url(self, obj: Review) -> str | None:
        url = obj.user.profile_img_url
        return url if url else None


# 리뷰 등록 요청 검증
class ReviewCreateSerializer(serializers.Serializer[None]):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(max_length=200)
    image_url = serializers.URLField(required=False, allow_null=True)
    route_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_image_url(self, value: str) -> str:
        return validate_s3_image_url(value)


# 리뷰 등록 응답
class ReviewCreateResponseSerializer(IsOwnerMixin, serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")
    route = ReviewRouteSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["user_id", "review_id", "rating", "content", "image_url", "created_at", "is_owner", "route"]


# 리뷰 수정 요청 검증
class ReviewUpdateSerializer(serializers.Serializer[None]):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    content = serializers.CharField(max_length=200, required=False)
    image_url = serializers.URLField(required=False, allow_null=True)
    route_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_image_url(self, value: str) -> str:
        return validate_s3_image_url(value)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("수정할 항목을 하나 이상 입력해야 합니다.")
        return attrs


# 리뷰 수정 응답
class ReviewUpdateResponseSerializer(IsOwnerMixin, serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")
    route = ReviewRouteSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["user_id", "review_id", "rating", "content", "image_url", "updated_at", "is_owner", "route"]
