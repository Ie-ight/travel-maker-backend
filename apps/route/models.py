from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampModel
from apps.place.models import Place, Tag


class Route(TimeStampModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="routes",
        verbose_name="작성자",
    )
    title = models.CharField(max_length=20, verbose_name="제목")
    description = models.TextField(null=True, blank=True, verbose_name="설명")
    region_tag = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="region_routes",
        verbose_name="지역 태그",
    )
    theme_tags = models.ManyToManyField(
        Tag,
        related_name="theme_routes",
        blank=True,
        verbose_name="테마 태그",
    )
    start_date = models.DateField(verbose_name="시작일")
    end_date = models.DateField(verbose_name="종료일")
    like_count = models.PositiveIntegerField(default=0, verbose_name="좋아요 수")

    class Meta:
        db_table = "routes"
        ordering = ["-created_at"]
        verbose_name = "경로"
        verbose_name_plural = "경로 목록"

    def __str__(self) -> str:
        return self.title


class RouteDay(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="days", verbose_name="경로")
    day_index = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="일차",
    )
    places = models.ManyToManyField(Place, through="RouteDayPlace", verbose_name="장소")  # type: ignore[var-annotated]

    class Meta:
        db_table = "route_days"
        unique_together = [("route", "day_index")]
        ordering = ["day_index"]
        verbose_name = "경로 일차"
        verbose_name_plural = "경로 일차 목록"

    def __str__(self) -> str:
        return f"{self.route.title} - {self.day_index}일차"


class RouteDayPlace(models.Model):
    route_day = models.ForeignKey(RouteDay, on_delete=models.CASCADE, related_name="day_places", verbose_name="일차")
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name="장소")
    order = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="순서",
    )

    class Meta:
        db_table = "route_day_places"
        unique_together = [("route_day", "order")]
        ordering = ["order"]
        verbose_name = "경로 장소"
        verbose_name_plural = "경로 장소 목록"


class RouteLike(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="likes", verbose_name="경로")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="route_likes",
        verbose_name="유저",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="좋아요 일시")

    class Meta:
        db_table = "route_likes"
        unique_together = [("route", "user")]
        verbose_name = "경로 좋아요"
        verbose_name_plural = "경로 좋아요 목록"

    def __str__(self) -> str:
        return f"{self.user} → {self.route.title}"
