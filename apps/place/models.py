from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.core.models import TimeStampModel


class Place(TimeStampModel):
    class ContentType(models.IntegerChoices):
        """Tour API contenttypeid → 관광 타입. 수집 대상 분류의 단일 소스(§2)."""

        TOURIST = 12, "관광지"
        CULTURE = 14, "문화시설"
        FESTIVAL = 15, "축제공연행사"
        COURSE = 25, "여행코스"
        LEPORTS = 28, "레포츠"
        LODGING = 32, "숙박"
        SHOPPING = 38, "쇼핑"
        FOOD = 39, "음식점"

    class LclsLarge(models.TextChoices):
        """Tour API lclsSystm1 대분류 9종. 분류 분기 로직의 단일 소스(§6).

        중분류(systm2)·소분류(systm3)는 코드가 수십~수백 종이고 lcls_codes.json(동적 sync)이
        이름까지 매핑하므로 enum으로 두지 않는다. 대분류만 분기에 쓰여 choices로 고정한다.
        """

        NATURE = "NA", "자연관광"
        HISTORY = "HS", "역사관광"
        CULTURE = "VE", "문화관광"
        FESTIVAL = "EV", "축제/공연/행사"
        EXPERIENCE = "EX", "체험관광"
        LEISURE = "LS", "레저스포츠"
        LODGING = "AC", "숙박"
        SHOPPING = "SH", "쇼핑"
        FOOD = "FD", "음식"

    place_name = models.CharField(max_length=100, verbose_name="장소명")
    latitude = models.DecimalField(max_digits=18, decimal_places=14, null=True, blank=True, verbose_name="위도")
    longitude = models.DecimalField(max_digits=18, decimal_places=14, null=True, blank=True, verbose_name="경도")
    rating_avg = models.DecimalField(max_digits=2, decimal_places=1, default=0, verbose_name="평균 별점")
    rating_count = models.PositiveIntegerField(default=0, verbose_name="평점 수")
    description = models.TextField(null=True, blank=True, verbose_name="설명")

    content_id = models.IntegerField(unique=True, verbose_name="Tour API 콘텐츠 ID")
    content_type_id = models.PositiveSmallIntegerField(
        db_index=True, choices=ContentType.choices, verbose_name="관광 타입 ID"
    )

    address_primary = models.CharField(max_length=255, null=True, blank=True, verbose_name="주소")
    address_detail = models.CharField(max_length=255, null=True, blank=True, verbose_name="상세 주소")
    tel = models.CharField(max_length=50, null=True, blank=True, verbose_name="전화번호")
    homepage = models.TextField(null=True, blank=True, verbose_name="홈페이지")
    zipcode = models.CharField(max_length=10, null=True, blank=True, verbose_name="우편번호")

    lcls_systm1 = models.CharField(
        max_length=20, choices=LclsLarge.choices, null=True, blank=True, verbose_name="분류 대분류"
    )
    lcls_systm2 = models.CharField(max_length=20, null=True, blank=True, verbose_name="분류 중분류")
    lcls_systm3 = models.CharField(max_length=20, null=True, blank=True, verbose_name="분류 소분류")

    source_modified_at = models.CharField(max_length=14, null=True, blank=True, verbose_name="원본 수정 일시")
    is_active = models.BooleanField(default=True, verbose_name="활성 여부")

    tags = models.ManyToManyField("Tag", related_name="places", blank=True, verbose_name="태그")  # type: ignore[var-annotated]

    class Meta:
        db_table = "places"
        indexes = [
            models.Index(fields=["place_name"]),
            # 활성 장소의 rating/review(rating_count) 내림차순 정렬 가속(부분 인덱스, id 동률 보조키 포함)
            models.Index(
                fields=["-rating_avg", "-id"], condition=models.Q(is_active=True), name="place_active_rating_idx"
            ),
            models.Index(
                fields=["-rating_count", "-id"], condition=models.Q(is_active=True), name="place_active_review_idx"
            ),
        ]
        verbose_name = "장소"
        verbose_name_plural = "장소 목록"

    def __str__(self) -> str:
        return self.place_name


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name="images", on_delete=models.CASCADE, verbose_name="장소")
    image_url = models.CharField(max_length=500, verbose_name="이미지 URL")
    thumbnail_url = models.CharField(max_length=500, null=True, blank=True, verbose_name="썸네일 URL")
    is_main = models.BooleanField(default=False, verbose_name="대표 이미지 여부")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="순서")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["place", "image_url"], name="unique_place_image_url"),
        ]
        ordering = ["order", "id"]
        verbose_name = "장소 이미지"
        verbose_name_plural = "장소 이미지 목록"


class Tag(models.Model):
    class TagType(models.TextChoices):
        """태그 분류 5종. 시드·결정론/AI 태깅이 참조하는 단일 소스(§8)."""

        TRAVEL_STYLE = "여행 스타일", "여행 스타일"
        SUB_THEME = "세부 테마", "세부 테마"
        COMPANION = "동행", "동행"
        REGION = "지역", "지역"
        FACILITY = "편의성", "편의성"

    tag_type = models.CharField(max_length=20, choices=TagType.choices, verbose_name="태그 유형")
    tag_name = models.CharField(max_length=20, unique=True, verbose_name="태그명")

    class Meta:
        verbose_name = "태그"
        verbose_name_plural = "태그 목록"

    def __str__(self) -> str:
        return self.tag_name


class PlaceInfo(models.Model):
    """detailIntro2 기반 운영 정보. Place와 1:1, 선택적(호출 전/실패해도 Place는 독립 동작)."""

    place = models.OneToOneField(
        Place, related_name="info", on_delete=models.CASCADE, primary_key=True, verbose_name="장소"
    )
    operating_hours = models.TextField(null=True, blank=True, verbose_name="운영시간")
    closed_days = models.TextField(null=True, blank=True, verbose_name="휴무일")
    parking = models.BooleanField(null=True, verbose_name="주차 가능 여부")
    admission_fee = models.TextField(null=True, blank=True, verbose_name="입장료")
    spend_time = models.TextField(null=True, blank=True, verbose_name="관람 소요시간")
    discount_info = models.TextField(null=True, blank=True, verbose_name="할인 정보")
    accom_count = models.TextField(null=True, blank=True, verbose_name="수용 인원")
    pet = models.BooleanField(null=True, verbose_name="반려동물 동반 가능")
    baby_carriage = models.BooleanField(null=True, verbose_name="유모차 동반 가능")
    credit_card = models.BooleanField(null=True, verbose_name="카드 결제 가능")

    class Meta:
        db_table = "place_info"
        verbose_name = "장소 운영정보"
        verbose_name_plural = "장소 운영정보 목록"


class PlaceFeature(TimeStampModel):
    """AI가 산출한 장소 성향 6차원 벡터(§4·§9). Place와 1:1, updated_at = 최신 계산 시각."""

    place = models.OneToOneField(
        Place, related_name="place_feature", on_delete=models.CASCADE, primary_key=True, verbose_name="장소"
    )
    style_vector = VectorField(dimensions=6, verbose_name="성향 벡터")

    class Meta:
        db_table = "place_features"
        verbose_name = "장소 성향 벡터"
        verbose_name_plural = "장소 성향 벡터 목록"
        indexes = [
            HnswIndex(
                name="place_style_vector_hnsw",
                fields=["style_vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]
