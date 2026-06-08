from drf_spectacular.utils import extend_schema

from apps.place.serializers.admin_place_serializers import (
    AdminPlaceCreateResponseSerializer,
    AdminPlaceCreateSerializer,
    AdminPlaceUpdateResponseSerializer,
    AdminPlaceUpdateSerializer,
)

admin_place_create_schema = extend_schema(
    summary="장소 등록 (관리자)",
    request=AdminPlaceCreateSerializer,
    responses={201: AdminPlaceCreateResponseSerializer},
)

admin_place_update_schema = extend_schema(
    summary="장소 수정 (관리자)",
    request=AdminPlaceUpdateSerializer,
    responses={200: AdminPlaceUpdateResponseSerializer},
)

admin_place_delete_schema = extend_schema(
    summary="장소 삭제 (관리자)",
    responses={200: {"type": "object", "properties": {"message": {"type": "string"}}}},
)
