from rest_framework import serializers

from apps.place.models import Place, Tag


class TagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "tag_name"]


class PlaceListSerializer(serializers.ModelSerializer[Place]):
    image_url = serializers.SerializerMethodField()
    bookmark_count = serializers.IntegerField(read_only=True)
    rating_avg = serializers.FloatField()  # DecimalField 기본(문자열) 대신 숫자로 (미평가=0)
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


class PlaceDetailSerializer(serializers.ModelSerializer[Place]):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    rating_avg = serializers.FloatField()  # 목록과 동일 (리뷰 없으면 0)
    review_count = serializers.IntegerField(read_only=True)
    bookmark_count = serializers.IntegerField(read_only=True)
    images = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)  # 기존 TagSerializer 재사용 (id, tag_name)

    def get_images(self, obj: Place) -> list[str]:
        # 대표 이미지 우선, 그다음 order. prefetch된 목록을 파이썬에서 정렬(추가 쿼리 없음)
        images = sorted(obj.images.all(), key=lambda i: (not i.is_main, i.order))
        return [image.image_url for image in images]

    class Meta:
        model = Place
        fields = [
            "id",
            "place_name",
            "description",
            "latitude",
            "longitude",
            "rating_avg",
            "review_count",
            "bookmark_count",
            "images",
            "tags",
        ]


class PlaceListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = PlaceListSerializer(many=True)


class PlaceErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error_detail = serializers.CharField()
