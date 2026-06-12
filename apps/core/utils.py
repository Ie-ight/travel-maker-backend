from django.conf import settings
from rest_framework import serializers


def validate_s3_image_url(value: str) -> str:
    if value and not value.startswith(f"https://{settings.AWS_STORAGE_BUCKET_NAME}"):
        raise serializers.ValidationError("유효하지 않은 이미지 URL입니다.")
    return value
