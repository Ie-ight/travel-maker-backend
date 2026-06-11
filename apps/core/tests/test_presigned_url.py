from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ParamValidationError

from apps.core.exceptions import BadRequest, ServiceUnavailable
from apps.core.presigned_url.s3_handler import S3Handler
from apps.core.presigned_url.serializers import PresignedUrlRequestSerializer
from apps.core.presigned_url.services import PresignedUrlService


class TestPresignedUrlRequestSerializer:
    def test_허용된_확장자_검증_성공(self) -> None:
        serializer = PresignedUrlRequestSerializer(data={"file_name": "프로필 사진.JPG"})

        serializer.is_valid(raise_exception=True)

        assert serializer.validated_data["content_type"] == "image/jpeg"
        assert serializer.validated_data["file_name"].endswith(".jpg")

    def test_허용되지_않은_확장자_400(self) -> None:
        serializer = PresignedUrlRequestSerializer(data={"file_name": "malware.exe"})

        with pytest.raises(BadRequest):
            serializer.is_valid()


class TestS3Handler:
    def test_presigned_url_생성_실패시_ServiceUnavailable(self) -> None:
        handler = S3Handler()
        handler.s3 = MagicMock()
        handler.s3.generate_presigned_url.side_effect = ParamValidationError(report="Invalid bucket name")

        with pytest.raises(ServiceUnavailable):
            handler.presigned_url_for_upload("profile-images/key.jpg", "image/jpeg")

    def test_key_from_img_url_버킷_URL이면_key_반환(self) -> None:
        handler = S3Handler()
        handler.bucket = "example-bucket"
        handler.region = "ap-northeast-2"

        url = "https://example-bucket.s3.ap-northeast-2.amazonaws.com/profiles/old.jpg"

        assert handler.key_from_img_url(url) == "profiles/old.jpg"

    def test_key_from_img_url_다른_도메인이면_None(self) -> None:
        handler = S3Handler()
        handler.bucket = "example-bucket"
        handler.region = "ap-northeast-2"

        assert handler.key_from_img_url("https://k.kakaocdn.net/profile.jpg") is None

    def test_delete_object_예외_무시(self) -> None:
        handler = S3Handler()
        handler.s3 = MagicMock()
        handler.s3.delete_object.side_effect = ParamValidationError(report="boom")

        handler.delete_object("profiles/old.jpg")  # 예외가 전파되지 않아야 함


class TestPresignedUrlService:
    def test_업로드_URL_생성(self) -> None:
        mock_handler = MagicMock()
        mock_handler.presigned_url_for_upload.return_value = "https://example.com/presigned"
        mock_handler.img_url.return_value = "https://example.com/profile-images/key.jpg"

        with patch("apps.core.presigned_url.services.get_s3_handler", return_value=mock_handler):
            result = PresignedUrlService.create_upload_urls(
                file_name="profile.jpg", content_type="image/jpeg", path="profile-images"
            )

        assert result["presigned_url"] == "https://example.com/presigned"
        assert result["img_url"] == "https://example.com/profile-images/key.jpg"
        assert result["key"].startswith("profile-images/")
        assert result["key"].endswith("_profile.jpg")
        assert result["content_type"] == "image/jpeg"
        mock_handler.presigned_url_for_upload.assert_called_once_with(result["key"], "image/jpeg", 600)

    def test_delete_by_img_url_버킷_객체면_삭제(self) -> None:
        mock_handler = MagicMock()
        mock_handler.key_from_img_url.return_value = "profiles/old.jpg"

        with patch("apps.core.presigned_url.services.get_s3_handler", return_value=mock_handler):
            PresignedUrlService.delete_by_img_url("https://example.com/profiles/old.jpg")

        mock_handler.delete_object.assert_called_once_with("profiles/old.jpg")

    def test_delete_by_img_url_버킷_객체가_아니면_삭제_안함(self) -> None:
        mock_handler = MagicMock()
        mock_handler.key_from_img_url.return_value = None

        with patch("apps.core.presigned_url.services.get_s3_handler", return_value=mock_handler):
            PresignedUrlService.delete_by_img_url("https://k.kakaocdn.net/profile.jpg")

        mock_handler.delete_object.assert_not_called()
