from rest_framework import serializers


class RecommendQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    region_tag_id = serializers.IntegerField(required=False, allow_null=True, default=None)
