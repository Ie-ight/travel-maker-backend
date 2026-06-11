from typing import Any

from celery import shared_task

from apps.core.s3 import compress_and_upload, delete_s3_object
from apps.user.models import User


@shared_task(bind=True, max_retries=3, default_retry_delay=5)  # type: ignore[misc]
def upload_profile_image(self: Any, user_id: int, image_data: bytes, content_type: str) -> None:
    try:
        key, url = compress_and_upload(image_data, content_type, folder="profiles")
    except Exception as exc:
        raise self.retry(exc=exc) from exc

    updated = User.objects.filter(pk=user_id).update(profile_img_url=url)
    if not updated:
        delete_s3_object(key)
