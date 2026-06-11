import uuid

from apps.core.presigned_url.s3_handler import get_s3_handler


class PresignedUrlService:
    @classmethod
    def create_upload_urls(cls, file_name: str, content_type: str, path: str, expire: int = 600) -> dict[str, str]:
        s3_handler = get_s3_handler()
        key = cls._key(file_name, path)
        presigned_url = s3_handler.presigned_url_for_upload(key, content_type, expire)
        img_url = s3_handler.img_url(key)
        return {"presigned_url": presigned_url, "img_url": img_url, "key": key, "content_type": content_type}

    @classmethod
    def delete_by_img_url(cls, img_url: str) -> None:
        s3_handler = get_s3_handler()
        key = s3_handler.key_from_img_url(img_url)
        if key:
            s3_handler.delete_object(key)

    @classmethod
    def _key(cls, file_name: str, path: str) -> str:
        return f"{path.rstrip('/')}/{cls._image_uuid()}_{file_name}"

    @staticmethod
    def _image_uuid() -> str:
        return str(uuid.uuid4())
