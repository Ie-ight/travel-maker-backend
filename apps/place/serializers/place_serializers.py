from rest_framework import serializers

from apps.place.models import Place, Tag


class TagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "tag_name"]


class PlaceListSerializer(serializers.ModelSerializer[Place]):
    image_url = serializers.SerializerMethodField()
    bookmark_count = serializers.IntegerField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    def get_image_url(self, obj: Place) -> str | None:
        image = obj.images.filter(is_main=True).first()
        return image.image_url if image else None

    class Meta:
        model = Place
        fields = [
            "id",
            "place_name",
            "image_url",
            "description",
            "bookmark_count",
            "rating_avg",
            "tags",
        ]


class PlaceListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = PlaceListSerializer(many=True)


class PlaceErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error_detail = serializers.CharField()
