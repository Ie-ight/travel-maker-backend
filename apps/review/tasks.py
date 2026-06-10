from typing import Any

from celery import shared_task

from apps.core.s3 import compress_and_upload, delete_s3_object
from apps.review.models import Review


@shared_task(bind=True, max_retries=3, default_retry_delay=5)  # type: ignore[misc]
def upload_review_image(self: Any, review_id: int, image_data: bytes, content_type: str) -> None:
    try:
        key, url = compress_and_upload(image_data, content_type, folder="reviews")
    except Exception as exc:
        raise self.retry(exc=exc) from exc

    updated = Review.objects.filter(pk=review_id).update(image_url=url)
    if not updated:
        delete_s3_object(key)
