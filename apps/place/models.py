from django.db import models

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
