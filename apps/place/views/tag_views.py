from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.place.schemas.tag_schemas import tag_list_schema
from apps.place.serializers.tag_serializers import TagQuerySerializer, TagSerializer
from apps.place.services.tag_services import TagService


class TagListView(APIView):
    permission_classes = [AllowAny]

    @tag_list_schema
    def get(self, request: Request) -> Response:
        query_serializer = TagQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        tag_type = query_serializer.validated_data.get("tag_type")
        tags = TagService.get_tags(tag_type)
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
