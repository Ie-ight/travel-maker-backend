from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class TravelType(models.Model):
    type_key = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=100, default="")
    image_url = models.URLField(max_length=500, default="")
    tags = models.ManyToManyField("place.Tag")

    class Meta:
        db_table = "travel_types"
        verbose_name = "여행 성향 유형"
        verbose_name_plural = "여행 성향 유형 목록"

    def __str__(self) -> str:
        return f"{self.type_key} - {self.name}"


class UserTestResult(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    travel_type = models.ForeignKey(TravelType, on_delete=models.CASCADE)
    result_vector = VectorField(dimensions=6)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_quiz_results"
        verbose_name = "유저 여행 성향 테스트 결과"
        verbose_name_plural = "유저 여행 성향 테스트 결과"

    def __str__(self) -> str:
        return f"{self.user} - {self.travel_type.type_key}"
