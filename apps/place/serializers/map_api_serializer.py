from rest_framework import serializers

from apps.place.models import Place


class PlaceMapSerializer(serializers.ModelSerializer[Place]):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    image_url = serializers.SerializerMethodField()
    rating_avg = serializers.FloatField()

    def get_image_url(self, obj: Place) -> str | None:
        image = obj.images.filter(is_main=True).first()
        return image.image_url if image else None

    class Meta:
        model = Place
        fields = ["id", "place_name", "latitude", "longitude", "image_url", "rating_avg"]


class RouteRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    origin_lat = serializers.FloatField()
    origin_lng = serializers.FloatField()
    place_id = serializers.IntegerField()


class RouteErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error_detail = serializers.CharField()
