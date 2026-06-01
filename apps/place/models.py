from django.db import models

from apps.core.models import TimeStampModel


class Place(TimeStampModel):
    place_name = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    rating_avg = models.DecimalField(max_digits=2, decimal_places=1, default=0)  # 평균 평점(미평가=0, 척도 1~5)
    rating_count = models.PositiveIntegerField(default=0)  # 평점 개수 - 계산 보정용
    description = models.TextField(null=True, blank=True)
    tags = models.ManyToManyField("Tag", related_name="places", blank=True)  # type: ignore[var-annotated]

    class Meta:
        db_table = "places"
        indexes = [models.Index(fields=["place_name"])]

    def __str__(self) -> str:
        return self.place_name


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name="images", on_delete=models.CASCADE)
    image_url = models.CharField(max_length=255, default="default_image_url")
    is_main = models.BooleanField(default=False)  # 메인 사진 구분용
    order = models.PositiveSmallIntegerField(default=0)  # 사진 순서


class Tag(models.Model):
    tag_type = models.CharField(max_length=20)
    tag_name = models.CharField(max_length=20, unique=True)
