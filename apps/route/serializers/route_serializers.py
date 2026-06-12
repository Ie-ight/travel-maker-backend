from typing import Any

from django.db.models import QuerySet
from rest_framework import serializers

from apps.place.models import PlaceImage
from apps.route.models import Route, RouteDay, RouteDayPlace


def _get_main_image_url(images: QuerySet[PlaceImage]) -> str | None:
    # 장소 대표 이미지(is_main=True) URL 반환. 목록·상세 모두 동일 로직이라 공통 헬퍼로 추출.
    # prefetch된 캐시를 활용하므로 추가 쿼리 없음.
    for image in images:
        if image.is_main:
            return str(image.image_url)
    return None


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
        # 날짜 검증: 시작일 <= 종료일, 최대 4박 5일(차이 ≤ 4일)
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
        # 수정 시 start_date/end_date 둘 다 있을 때만 날짜 검증 (부분 수정 허용)
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
    # 서비스에서 annotate(place_count=Count(...))로 계산된 값을 그대로 직렬화
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
        # 1일차 첫 번째 장소의 대표 이미지를 카드 썸네일로 사용.
        # prefetch된 캐시를 활용하므로 추가 쿼리 없음 (.filter() 대신 인덱스 접근)
        try:
            first_dp = obj.days.all()[0].day_places.all()[0]
            return _get_main_image_url(first_dp.place.images.all())
        except (IndexError, AttributeError):
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


class RouteLikeResponseSerializer(serializers.Serializer[dict[str, str | int]]):
    message = serializers.CharField()
    like_id = serializers.IntegerField()
    like_count = serializers.IntegerField()


class RouteDayPlaceDetailSerializer(serializers.ModelSerializer[RouteDayPlace]):
    place_id = serializers.IntegerField(source="place.id")
    place_name = serializers.CharField(source="place.place_name")
    # latitude/longitude: 지도에서 장소 간 선(경로)을 그리는 핵심 좌표 데이터
    # order 순서대로 정렬되어 있어 프론트가 순서대로 선을 연결하면 됨
    latitude = serializers.FloatField(source="place.latitude")
    longitude = serializers.FloatField(source="place.longitude")
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = RouteDayPlace
        fields = ["order", "place_id", "place_name", "latitude", "longitude", "image_url"]
        read_only_fields = fields

    def get_image_url(self, obj: RouteDayPlace) -> str | None:
        return _get_main_image_url(obj.place.images.all())


class RouteDayDetailSerializer(serializers.ModelSerializer[RouteDay]):
    # source="day_places": RouteDay → RouteDayPlace 역방향 related_name
    places = RouteDayPlaceDetailSerializer(source="day_places", many=True)

    class Meta:
        model = RouteDay
        fields = ["day_index", "places"]
        read_only_fields = fields


class RouteDetailSerializer(RouteListSerializer):
    # RouteListSerializer를 상속해 get_region_tag·get_theme_tags 중복 제거.
    # days 필드만 추가하고 Meta.fields를 재정의해 상세 응답에 맞게 조정.
    # day_index 오름차순 → 각 day 안에서 order 오름차순으로 정렬된 상태로 반환.
    # 프론트는 days[0].places → days[1].places 순서로 선을 이으면 전체 경로 완성.
    days = RouteDayDetailSerializer(many=True)

    class Meta(RouteListSerializer.Meta):
        fields = [
            "route_id",
            "title",
            "description",
            "region_tag",
            "theme_tags",
            "start_date",
            "end_date",
            "like_count",
            "created_at",
            "days",
        ]
        read_only_fields = fields
