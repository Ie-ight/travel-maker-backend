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
    )
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField(max_length=200)
    image_url = models.URLField(max_length=512, null=True, blank=True)  # 모델과 시리얼라이저 타입 일치

    class Meta:
        unique_together = ("user", "place")
        ordering = ["-id"]
