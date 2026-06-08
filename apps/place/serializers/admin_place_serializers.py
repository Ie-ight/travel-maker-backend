from rest_framework import serializers

from apps.place.models import Place


class AdminPlaceCreateSerializer(serializers.Serializer[None]):
    place_name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=18, decimal_places=14)
    longitude = serializers.DecimalField(max_digits=18, decimal_places=14)
    content_id = serializers.IntegerField(required=False, allow_null=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    image_urls = serializers.ListField(child=serializers.URLField(), required=False, default=list)


class AdminPlaceUpdateSerializer(serializers.Serializer[None]):
    place_name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=18, decimal_places=14)
    longitude = serializers.DecimalField(max_digits=18, decimal_places=14)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    image_urls = serializers.ListField(child=serializers.URLField(), required=False, default=list)


class AdminPlaceCreateResponseSerializer(serializers.ModelSerializer[Place]):
    class Meta:
        model = Place
        fields = ["id", "place_name", "created_at"]
        read_only_fields = fields


class AdminPlaceUpdateResponseSerializer(serializers.ModelSerializer[Place]):
    class Meta:
        model = Place
        fields = ["id", "place_name", "updated_at"]
        read_only_fields = fields
