from django.conf import settings
from rest_framework import serializers

from apps.review.models import Review


# 리뷰 목록 응답(닉네임 포함)
class ReviewListItemSerializer(serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")
    user_nickname = serializers.CharField(source="user.nickname")

    class Meta:
        model = Review
        fields = ["review_id", "user_id", "user_nickname", "rating", "content", "image_url", "created_at", "updated_at"]


# 리뷰 등록 요청 검증
class ReviewCreateSerializer(serializers.Serializer[None]):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(max_length=200)
    image = serializers.ImageField(required=False, allow_null=True)


# 리뷰 등록 응답
class ReviewCreateResponseSerializer(serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")

    class Meta:
        model = Review
        fields = ["user_id", "review_id", "rating", "content", "image_url", "created_at"]


# 리뷰 수정 요청 검증
class ReviewUpdateSerializer(serializers.Serializer[None]):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    content = serializers.CharField(max_length=200, required=False)
    image_url = serializers.URLField(required=False, allow_null=True)

    def validate_image_url(self, value: str) -> str:
        if value and not value.startswith(f"https://{settings.AWS_STORAGE_BUCKET_NAME}"):
            raise serializers.ValidationError("유효하지 않은 이미지 URL입니다.")
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("수정할 항목을 하나 이상 입력해야 합니다.")
        return attrs


# 리뷰 수정 응답
class ReviewUpdateResponseSerializer(serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")

    class Meta:
        model = Review
        fields = ["user_id", "review_id", "rating", "content", "image_url", "updated_at"]
