from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimeStampModel


class Place(TimeStampModel):
    place_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=18, decimal_places=14, null=True, blank=True)
    longitude = models.DecimalField(max_digits=18, decimal_places=14, null=True, blank=True)
    rating_avg = models.DecimalField(max_digits=2, decimal_places=1, default=0)  # 평균 평점(미평가=0, 척도 1~5)
    rating_count = models.PositiveIntegerField(default=0)  # 평점 개수 - 계산 보정용
    description = models.TextField(null=True, blank=True)  # AI 성향 분석 입력 텍스트(overview)

    content_id = models.IntegerField(unique=True, db_index=True)  # Tour API 고유 식별자
    content_type_id = models.PositiveSmallIntegerField(db_index=True)  # 관광타입 ID(12 관광지, 14 문화시설 등)

    address_primary = models.CharField(max_length=255, null=True, blank=True)
    address_detail = models.CharField(max_length=255, null=True, blank=True)
    tel = models.CharField(max_length=50, null=True, blank=True)
    homepage = models.TextField(null=True, blank=True)  # 원문 HTML이 올 수 있어 TextField
    zipcode = models.CharField(max_length=10, null=True, blank=True)

    lcls_systm1 = models.CharField(max_length=20, null=True, blank=True, db_index=True)  # 분류체계 대분류
    lcls_systm2 = models.CharField(max_length=20, null=True, blank=True, db_index=True)  # 분류체계 중분류
    lcls_systm3 = models.CharField(max_length=20, null=True, blank=True, db_index=True)  # 분류체계 소분류

    # 증분 동기화(단계 7): 목록 modifiedtime(YYYYMMDDHHMMSS 원문). 저장값보다 크면 변경으로 보고 재수집
    source_modified_at = models.CharField(max_length=14, null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)  # 소프트삭제(showflag=0). 비공개/삭제 시 False

    tags = models.ManyToManyField("Tag", related_name="places", blank=True)  # type: ignore[var-annotated]

    class Meta:
        db_table = "places"
        # content_id(unique)·content_type_id(db_index)·lcls_systm*(db_index)는 필드에서 이미 인덱싱됨
        indexes = [models.Index(fields=["place_name"])]

    def __str__(self) -> str:
        return self.place_name


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name="images", on_delete=models.CASCADE)
    image_url = models.CharField(max_length=500)
    thumbnail_url = models.CharField(max_length=500, null=True, blank=True)
    is_main = models.BooleanField(default=False)  # 메인 사진 구분용
    order = models.PositiveSmallIntegerField(default=0)  # 사진 순서

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["place", "image_url"], name="unique_place_image_url"),
        ]
        ordering = ["order", "id"]


class Tag(models.Model):
    tag_type = models.CharField(max_length=20)
    tag_name = models.CharField(max_length=20, unique=True)


class PlaceInfo(models.Model):
    """detailIntro2 기반 운영 정보. Place와 1:1, 선택적(호출 전/실패해도 Place는 독립 동작)."""

    place = models.OneToOneField(Place, related_name="info", on_delete=models.CASCADE)
    operating_hours = models.TextField(null=True, blank=True)  # 운영시간
    closed_days = models.TextField(null=True, blank=True)  # 휴무일
    parking = models.BooleanField(null=True)  # 주차 가능 여부
    admission_fee = models.TextField(null=True, blank=True)  # 입장료 원문
    spend_time = models.CharField(max_length=50, null=True, blank=True)  # 관람소요시간
    discount_info = models.TextField(null=True, blank=True)  # 할인정보
    accom_count = models.CharField(max_length=50, null=True, blank=True)  # 수용인원
    pet = models.BooleanField(null=True)  # 반려동물 동반 가능
    baby_carriage = models.BooleanField(null=True)  # 유모차 동반 가능
    credit_card = models.BooleanField(null=True)  # 카드 결제 가능

    class Meta:
        db_table = "place_info"


class PlaceFeature(TimeStampModel):
    """AI가 산출한 장소 성향 6차원 벡터(§4·§9). Place와 1:1, updated_at = 최신 계산 시각."""

    place = models.OneToOneField(Place, related_name="place_feature", on_delete=models.CASCADE)
    style_vector = VectorField(dimensions=6)

    class Meta:
        db_table = "place_features"
