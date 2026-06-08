from rest_framework import serializers

from apps.user.models import User


class AdminUserListSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "nickname", "email", "is_active", "created_at"]
        read_only_fields = fields
