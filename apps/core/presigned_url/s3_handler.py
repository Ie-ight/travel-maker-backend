import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.core.exceptions import ServiceUnavailable


class S3Handler:
    def __init__(self) -> None:
        self.s3 = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION_NAME,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.region = settings.AWS_S3_REGION_NAME

    def presigned_url_for_upload(self, key: str, content_type: str, expire: int = 600) -> str:
        try:
            return str(
                self.s3.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                    ExpiresIn=expire,
                )
            )
        except (BotoCoreError, ClientError) as exc:
            raise ServiceUnavailable("이미지 업로드 URL 발급에 실패했습니다.") from exc

    def img_url(self, key: str) -> str:
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def key_from_img_url(self, url: str) -> str | None:
        prefix = self.img_url("")
        if not url.startswith(prefix):
            return None
        return url.removeprefix(prefix)

    def delete_object(self, key: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            pass


s3_handler: S3Handler | None = None


def get_s3_handler() -> S3Handler:
    global s3_handler
    if s3_handler is None:
        s3_handler = S3Handler()
    return s3_handler
