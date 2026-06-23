from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.place.serializers.place_serializers import PlaceErrorResponseSerializer, PlaceListResponseSerializer

place_recommend_schema = extend_schema(
    tags=["Place"],
    summary="장소 추천",
    description="퀴즈 결과 벡터 기반 코사인 유사도 추천. 퀴즈 미완료 또는 비로그인 시 북마크 수 인기순으로 폴백.",
    parameters=[
        OpenApiParameter(
            name="tags",
            type=int,
            many=True,
            description="태그 ID 다중 선택: tags=1&tags=3 또는 tags=1,3",
        ),
        OpenApiParameter(name="region_tag_id", type=int, description="지역 태그 ID"),
        OpenApiParameter(name="page", type=int, description="페이지 번호 (기본 1)"),
        OpenApiParameter(name="page_size", type=int, description="페이지 크기 (기본 12, 최대 100)"),
    ],
    responses={200: PlaceListResponseSerializer, 400: PlaceErrorResponseSerializer},
)
