from rest_framework import serializers

from apps.review.models import Review


class AdminReviewListSerializer(serializers.ModelSerializer[Review]):
    class Meta:
        model = Review
        fields = ["id", "user_id", "place_id", "rating", "content", "created_at"]
        read_only_fields = fields
