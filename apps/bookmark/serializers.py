from typing import Any

from rest_framework import serializers

from apps.bookmark.models import Bookmark


class PlaceSimpleSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    place_name = serializers.CharField()
    rating_avg = serializers.DecimalField(max_digits=2, decimal_places=1)
    main_image = serializers.SerializerMethodField()

    def get_main_image(self, obj: Any) -> str | None:
        for image in obj.images.all():
            if image.is_main:
                return str(image.image_url)
        return None


class BookmarkSerializer(serializers.ModelSerializer[Bookmark]):
    place = PlaceSimpleSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ["id", "place", "created_at"]


class BookmarkCreateSerializer(serializers.ModelSerializer[Bookmark]):
    class Meta:
        model = Bookmark
        fields = ["place"]


class BookmarkCreateResponseSerializer(serializers.Serializer[Any]):
    message = serializers.CharField()
    bookmark_id = serializers.IntegerField()
