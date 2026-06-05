# apps/bookmark/models.py

from django.conf import settings
from django.db import models


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        db_column="user_id",
        verbose_name="유저",
    )
    place = models.ForeignKey(
        "place.Place",
        on_delete=models.CASCADE,
        related_name="bookmarks",
        db_column="place_id",
        verbose_name="장소",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="북마크 일시")

    class Meta:
        db_table = "bookmarks"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "place"],
                name="unique_user_place_bookmark",
            )
        ]
        ordering = ["-id"]
        verbose_name = "북마크"
        verbose_name_plural = "북마크 목록"

    def __str__(self) -> str:
        return f"[Bookmark] user={self.user_id} / place={self.place_id}"  # type: ignore[attr-defined]
