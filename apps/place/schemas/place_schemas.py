from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.place.serializers.place_serializers import (
    PlaceDetailSerializer,
    PlaceErrorResponseSerializer,
    PlaceListResponseSerializer,
)

place_list_schema = extend_schema(
    tags=["Place"],
    summary="장소 목록 조회",
    description="활성 장소 전체를 북마크 수 기준 내림차순으로 반환합니다.",
    parameters=[
        OpenApiParameter(name="page", type=int, description="페이지 번호: 0보다 작거나 없는 페이지는 404"),
        OpenApiParameter(name="page_size", type=int, description="목록 출력 개수: 기본 8, 최대 100"),
    ],
    responses={200: PlaceListResponseSerializer, 404: PlaceErrorResponseSerializer},
)


place_search_schema = extend_schema(
    tags=["Place"],
    summary="장소 검색",
    description="장소명 키워드로 검색합니다. 키워드 없이 호출하면 전체 목록과 동일합니다.",
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
    summary="장소 태그 필터",
    description="태그 ID로 AND 필터링합니다. 선택한 태그를 모두 포함한 장소만 반환합니다.",
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
    summary="장소 상세 조회",
    description="장소 ID로 상세 정보를 반환합니다.",
    responses={200: PlaceDetailSerializer, 404: PlaceErrorResponseSerializer},
)
