from rest_framework import serializers

from apps.user.models import Follow


class FollowerListSerializer(serializers.ModelSerializer[Follow]):
    """팔로워 목록 응답 — Follow.follower(나를 팔로우하는 사람)를 노출"""

    user_id = serializers.IntegerField(source="follower.id")
    nickname = serializers.CharField(source="follower.nickname")
    profile_img_url = serializers.CharField(source="follower.profile_img_url")

    class Meta:
        model = Follow
        fields = ["user_id", "nickname", "profile_img_url"]
        read_only_fields = fields


class FollowingListSerializer(serializers.ModelSerializer[Follow]):
    """팔로잉 목록 응답 — Follow.following(내가 팔로우하는 사람)을 노출"""

    user_id = serializers.IntegerField(source="following.id")
    nickname = serializers.CharField(source="following.nickname")
    profile_img_url = serializers.CharField(source="following.profile_img_url")

    class Meta:
        model = Follow
        fields = ["user_id", "nickname", "profile_img_url"]
        read_only_fields = fields


class FollowActionResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    detail = serializers.CharField()
