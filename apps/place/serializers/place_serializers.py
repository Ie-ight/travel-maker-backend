from rest_framework import serializers

from apps.place.models import Place, PlaceInfo, Tag


class TagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "tag_name"]


class PlaceInfoSerializer(serializers.ModelSerializer[PlaceInfo]):
    """detailIntro2 기반 운영 정보(상세 페이지 디테일). boolean은 가능/불가/정보없음(null)."""

    class Meta:
        model = PlaceInfo
        fields = [
            "operating_hours",
            "closed_days",
            "parking",
            "admission_fee",
            "spend_time",
            "discount_info",
            "accom_count",
            "pet",
            "baby_carriage",
            "credit_card",
        ]


class PlaceListSerializer(serializers.ModelSerializer[Place]):
    image_url = serializers.SerializerMethodField()
    bookmark_count = serializers.IntegerField(read_only=True)
    is_bookmarked = serializers.BooleanField(read_only=True)
    rating_avg = serializers.FloatField()  # DecimalField 기본(문자열) 대신 숫자로 (미평가=0)
    review_count = serializers.IntegerField(source="rating_count", read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    def get_image_url(self, obj: Place) -> str | None:
        for image in obj.images.all():  # prefetch 캐시 활용 — .filter()는 캐시 무시
            if image.is_main:
                return image.image_url
        return None

    class Meta:
        model = Place
        fields = [
            "id",
            "place_name",
            "image_url",
            "description",
            "latitude",
            "longitude",
            "review_count",
            "bookmark_count",
            "is_bookmarked",
            "rating_avg",
            "tags",
        ]


class PlaceDetailSerializer(serializers.ModelSerializer[Place]):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    rating_avg = serializers.FloatField()  # 목록과 동일 (리뷰 없으면 0)
    review_count = serializers.IntegerField(source="rating_count", read_only=True)  # 비정규화 컬럼(= 리뷰 수)
    is_bookmarked = serializers.BooleanField(read_only=True)
    images = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)  # 기존 TagSerializer 재사용 (id, tag_name)
    # PlaceInfo 운영정보(역방향 1:1, obj.info). 없는 장소(14%)는 allow_null로 null 직렬화.
    info = PlaceInfoSerializer(read_only=True, allow_null=True)

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
            "homepage",
            "tel",
            "address_primary",
            "address_detail",
            "rating_avg",
            "review_count",
            "is_bookmarked",
            "images",
            "tags",
            "info",
        ]


class PlaceListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = PlaceListSerializer(many=True)


class PlaceErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error_detail = serializers.CharField()
