from rest_framework import serializers


class RecommendQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    region_tag_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
