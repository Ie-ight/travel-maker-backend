from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminRole
from apps.place.schemas.admin_place_schemas import (
    admin_place_create_schema,
    admin_place_delete_schema,
    admin_place_update_schema,
)
from apps.place.serializers.admin_place_serializers import (
    AdminPlaceCreateResponseSerializer,
    AdminPlaceCreateSerializer,
    AdminPlaceUpdateResponseSerializer,
    AdminPlaceUpdateSerializer,
)
from apps.place.services.admin_place_service import (
    admin_create_place,
    admin_delete_place,
    admin_update_place,
)


class AdminPlaceListCreateView(APIView):
    permission_classes = [IsAdminRole]

    @admin_place_create_schema
    def post(self, request: Request) -> Response:
        serializer = AdminPlaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        place = admin_create_place(dict(serializer.validated_data))
        return Response(AdminPlaceCreateResponseSerializer(place).data, status=status.HTTP_201_CREATED)


class AdminPlaceDetailView(APIView):
    permission_classes = [IsAdminRole]

    @admin_place_update_schema
    def put(self, request: Request, place_id: int) -> Response:
        serializer = AdminPlaceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        place = admin_update_place(place_id, dict(serializer.validated_data))
        return Response(AdminPlaceUpdateResponseSerializer(place).data)

    @admin_place_delete_schema
    def delete(self, request: Request, place_id: int) -> Response:
        admin_delete_place(place_id)
        return Response({"message": "장소가 삭제되었습니다."})
