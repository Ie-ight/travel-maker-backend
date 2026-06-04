from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.place.serializers.map_api_serializer import (
    PlaceMapSerializer,
    RouteErrorResponseSerializer,
)

place_map_schema = extend_schema(
    tags=["Place Map"],
    summary="지도용 장소 목록",
    description="지도에 마커를 찍기 위한 전체 장소 좌표 목록을 반환합니다.",
    responses={200: PlaceMapSerializer(many=True)},
)

place_route_schema = extend_schema(
    tags=["Place Map"],
    summary="장소까지 경로 조회",
    description="사용자 현재 GPS 좌표(origin_lat, origin_lng)에서 장소(place_id)까지의 자동차 경로를 반환합니다.",
    parameters=[
        OpenApiParameter(name="origin_lat", type=float, required=True, description="출발지 위도"),
        OpenApiParameter(name="origin_lng", type=float, required=True, description="출발지 경도"),
        OpenApiParameter(name="place_id", type=int, required=True, description="목적지 장소 ID"),
    ],
    responses={
        200: {"type": "object", "description": "Kakao Mobility Directions API 응답 원문"},
        400: RouteErrorResponseSerializer,
        404: RouteErrorResponseSerializer,
    },
)
