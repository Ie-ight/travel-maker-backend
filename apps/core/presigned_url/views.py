from typing import Any

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.presigned_url.serializers import (
    PresignedUrlRequestSerializer,
    PresignedUrlResponseSerializer,
)
from apps.core.presigned_url.services import PresignedUrlService


class PresignedUrlView(APIView):
    permission_classes: list[type[Any]] = []
    path: str
    expire: int = 600

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "path"):
            raise TypeError(f"{cls.__name__}에 path 클래스 변수를 정의해야 합니다")
        if not isinstance(cls.path, str):
            raise TypeError(f"{cls.__name__}: path는 str이어야 합니다.")
        if not isinstance(cls.expire, int):
            raise TypeError(f"{cls.__name__}: expire는 int여야 합니다.")

    def handle_request(self, request: Request) -> Response:
        request_serializer = PresignedUrlRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        urls = PresignedUrlService.create_upload_urls(
            file_name=request_serializer.validated_data["file_name"],
            content_type=request_serializer.validated_data["content_type"],
            path=self.path,
            expire=self.expire,
        )
        response_serializer = PresignedUrlResponseSerializer(instance=urls)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
