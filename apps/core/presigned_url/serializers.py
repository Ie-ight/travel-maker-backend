from pathlib import Path

from django.utils.text import slugify
from rest_framework import serializers

from apps.core.exceptions import BadRequest
from apps.core.presigned_url.constants import ALLOWED_SUFFIX


class PresignedUrlRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    file_name = serializers.CharField(max_length=100)

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        file_name = attrs["file_name"]
        path = Path(file_name)
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_SUFFIX:
            raise BadRequest("지원하지 않는 파일 형식입니다.")

        stem = path.stem
        slugified_stem = slugify(stem, allow_unicode=True)
        attrs["file_name"] = slugified_stem + suffix
        attrs["content_type"] = ALLOWED_SUFFIX[suffix]
        return attrs


class PresignedUrlResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    presigned_url = serializers.CharField()
    img_url = serializers.CharField()
    key = serializers.CharField()
    content_type = serializers.CharField()
