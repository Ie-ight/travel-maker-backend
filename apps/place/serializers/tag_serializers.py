from typing import Any

from rest_framework import serializers

from apps.place.models import Tag


class TagSerializer(serializers.ModelSerializer["Tag"]):
    class Meta:
        model = Tag
        fields = ["id", "tag_name", "tag_type"]


class TagQuerySerializer(serializers.Serializer[Any]):
    tag_type = serializers.CharField(required=False)

    def validate_tag_type(self, value: str) -> str:
        valid_types = Tag.objects.values_list("tag_type", flat=True).distinct()  # type: ignore[attr-defined]
        if value not in valid_types:
            raise serializers.ValidationError("유효하지 않은 tag_type입니다.")
        return value
