from typing import Any

from rest_framework import serializers

from apps.route.models import Route


class RouteDayInputSerializer(serializers.Serializer[None]):
    day_index = serializers.IntegerField(min_value=1, max_value=5)
    place_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=5)


class RouteCreateSerializer(serializers.Serializer[None]):
    title = serializers.CharField(max_length=20)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    region_tag_id = serializers.IntegerField()
    theme_tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    days = RouteDayInputSerializer(many=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start_date = attrs["start_date"]
        end_date = attrs["end_date"]
        if start_date > end_date:
            raise serializers.ValidationError("시작일이 종료일보다 늦을 수 없습니다.")
        if (end_date - start_date).days > 4:
            raise serializers.ValidationError("최대 4박 5일까지 설정할 수 있습니다.")
        return attrs


class RouteUpdateSerializer(serializers.Serializer[None]):
    title = serializers.CharField(max_length=20, required=False)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    region_tag_id = serializers.IntegerField(required=False)
    theme_tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    days = RouteDayInputSerializer(many=True, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("시작일이 종료일보다 늦을 수 없습니다.")
            if (end_date - start_date).days > 4:
                raise serializers.ValidationError("최대 4박 5일까지 설정할 수 있습니다.")
        return attrs


class RouteCreateResponseSerializer(serializers.ModelSerializer[Route]):
    route_id = serializers.IntegerField(source="id")

    class Meta:
        model = Route
        fields = ["route_id", "title", "created_at"]
        read_only_fields = fields


class RouteUpdateResponseSerializer(serializers.ModelSerializer[Route]):
    route_id = serializers.IntegerField(source="id")

    class Meta:
        model = Route
        fields = ["route_id", "title", "updated_at"]
        read_only_fields = fields


class RouteListSerializer(serializers.ModelSerializer[Route]):
    route_id = serializers.IntegerField(source="id")
    image_url = serializers.SerializerMethodField()
    place_count = serializers.IntegerField(read_only=True)
    region_tag = serializers.SerializerMethodField()
    theme_tags = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            "route_id",
            "title",
            "description",
            "image_url",
            "place_count",
            "like_count",
            "created_at",
            "region_tag",
            "theme_tags",
        ]
        read_only_fields = fields

    def get_image_url(self, obj: Route) -> str | None:
        try:
            first_day = obj.days.all()[0]
            first_dp = first_day.day_places.all()[0]
            for image in first_dp.place.images.all():
                if image.is_main:
                    return image.image_url
        except (IndexError, AttributeError):
            pass
        return None

    def get_region_tag(self, obj: Route) -> str | None:
        return obj.region_tag.tag_name if obj.region_tag else None

    def get_theme_tags(self, obj: Route) -> list[str]:
        return [tag.tag_name for tag in obj.theme_tags.all()]


class RouteMyListSerializer(RouteListSerializer):
    class Meta(RouteListSerializer.Meta):
        fields = [
            "route_id",
            "title",
            "description",
            "image_url",
            "place_count",
            "like_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RouteLikeResponseSerializer(serializers.Serializer[Any]):
    message = serializers.CharField()
    like_id = serializers.IntegerField()
    like_count = serializers.IntegerField()
