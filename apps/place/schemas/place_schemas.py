from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.place.serializers.place_serializers import (
    PlaceDetailSerializer,
    PlaceErrorResponseSerializer,
    PlaceListResponseSerializer,
)

place_list_schema = extend_schema(
    tags=["Place"],
    parameters=[
        OpenApiParameter(name="page", type=int, description="페이지 번호: 0보다 작거나 없는 페이지는 404"),
        OpenApiParameter(name="page_size", type=int, description="목록 출력 개수: 기본 8, 최대 100"),
    ],
    responses={200: PlaceListResponseSerializer, 404: PlaceErrorResponseSerializer},
)


place_search_schema = extend_schema(
    tags=["Place"],
    parameters=[
        OpenApiParameter(name="keyword", type=str, description="place_name 부분 검색어 (없으면 전체 목록)"),
        OpenApiParameter(name="sort", type=str, description="정렬 기준: bookmark(기본) | review | rating"),
        OpenApiParameter(name="order", type=str, description="정렬 방향: desc(기본) | asc"),
        OpenApiParameter(name="page", type=int, description="페이지 번호: 0보다 작거나 없는 페이지는 404"),
        OpenApiParameter(name="page_size", type=int, description="목록 출력 개수: 기본 8, 최대 100"),
    ],
    responses={200: PlaceListResponseSerializer, 404: PlaceErrorResponseSerializer},
)

place_filter_schema = extend_schema(
    tags=["Place"],
    parameters=[
        OpenApiParameter(
            name="tags",
            type=int,
            many=True,
            description="태그 ID 다중 선택(AND): 모두 포함한 장소만. 예) tags=1&tags=3",
        ),
        OpenApiParameter(name="keyword", type=str, description="place_name 부분 검색어 (없으면 전체 목록)"),
        OpenApiParameter(name="sort", type=str, description="정렬 기준: bookmark(기본) | review | rating"),
        OpenApiParameter(name="order", type=str, description="정렬 방향: desc(기본) | asc"),
        OpenApiParameter(name="page", type=int, description="페이지 번호: 0보다 작거나 없는 페이지는 404"),
        OpenApiParameter(name="page_size", type=int, description="목록 출력 개수: 기본 8, 최대 100"),
    ],
    responses={200: PlaceListResponseSerializer, 404: PlaceErrorResponseSerializer},
)

place_detail_schema = extend_schema(
    tags=["Place"],
    responses={200: PlaceDetailSerializer, 404: PlaceErrorResponseSerializer},
)
