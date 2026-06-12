from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampModel
from apps.place.models import Place


class Review(TimeStampModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="작성자",
    )
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="reviews", verbose_name="장소")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="별점"
    )
    content = models.TextField(max_length=200, verbose_name="내용")
    image_url = models.URLField(max_length=512, null=True, blank=True, verbose_name="이미지 URL")
    route = models.ForeignKey(
        "route.Route",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
        verbose_name="연결된 경로",
    )

    class Meta:
        unique_together = ("user", "place")
        ordering = ["-id"]
        verbose_name = "리뷰"
        verbose_name_plural = "리뷰 목록"
