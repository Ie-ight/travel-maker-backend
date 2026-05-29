from typing import Any

from rest_framework import serializers

from apps.bookmark.models import Bookmark
from apps.place.models import PlaceImage


class PlaceSimpleSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    place_name = serializers.CharField()
    rating_avg = serializers.DecimalField(max_digits=2, decimal_places=1)
    main_image = serializers.SerializerMethodField()

    def get_main_image(self, obj: Any) -> str | None:
        image = PlaceImage.objects.filter(place=obj, is_main=True).first()
        return image.image_url if image else None


class BookmarkSerializer(serializers.ModelSerializer[Bookmark]):
    place = PlaceSimpleSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ["id", "place", "created_at"]


class BookmarkCreateSerializer(serializers.ModelSerializer[Bookmark]):
    class Meta:
        model = Bookmark
        fields = ["place"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user = self.context["request"].user
        place = attrs["place"]
        if Bookmark.objects.filter(user=user, place=place).exists():
            raise serializers.ValidationError("이미 북마크한 여행지입니다.")
        return attrs
