from rest_framework import serializers

from apps.place.models import Tag


class TagSerializer(serializers.ModelSerializer["Tag"]):
    class Meta:
        model = Tag
        fields = ["id", "tag_name", "tag_type"]
