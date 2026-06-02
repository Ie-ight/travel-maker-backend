from rest_framework import serializers

from apps.review.models import Review


# 리뷰 목록 응답(닉네임 포함)
class ReviewListItemSerializer(serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")
    user_nickname = serializers.CharField(source="user.nickname")

    class Meta:
        model = Review
        fields = ["review_id", "user_id", "user_nickname", "rating", "content", "created_at", "updated_at"]


# 리뷰 등록 요청 검증
class ReviewCreateSerializer(serializers.Serializer[None]):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(max_length=200)


# 리뷰 등록 응답
class ReviewCreateResponseSerializer(serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")

    class Meta:
        model = Review
        fields = ["user_id", "review_id", "rating", "content", "created_at"]


# 리뷰 수정 요청 검증
class ReviewUpdateSerializer(serializers.Serializer[None]):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    content = serializers.CharField(max_length=200, required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("rating 또는 content 중 하나는 필수입니다.")
        return attrs


# 리뷰 수정 응답
class ReviewUpdateResponseSerializer(serializers.ModelSerializer[Review]):
    review_id = serializers.IntegerField(source="id")

    class Meta:
        model = Review
        fields = ["user_id", "review_id", "rating", "content", "updated_at"]
