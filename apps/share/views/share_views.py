from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.share.schemas.share_schemas import share_create_schema
from apps.share.serializers.share_serializers import ShareRequestSerializer, ShareResponseSerializer
from apps.share.services.share_services import generate_share_url


class ShareView(APIView):
    permission_classes = [AllowAny]

    @share_create_schema
    def post(self, request: Request) -> Response:
        serializer = ShareRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        share_url = generate_share_url(
            content_type=data["content_type"],
            content_id=data.get("content_id"),
            type_key=data.get("type_key"),
            vector=data.get("vector"),
        )
        return Response(
            ShareResponseSerializer({"share_url": share_url}).data,
            status=status.HTTP_200_OK,
        )
