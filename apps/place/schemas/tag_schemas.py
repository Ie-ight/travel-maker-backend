from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from apps.place.serializers.tag_serializers import TagSerializer

tag_list_schema = extend_schema(
    tags=["Tag"],
    summary="태그 목록 조회",
    description="태그 목록을 조회합니다. tag_type으로 그룹 필터 가능.",
    parameters=[
        OpenApiParameter(
            name="tag_type",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="태그 타입 필터 (예: 분위기)",
        )
    ],
    responses={
        200: TagSerializer(many=True),
        400: OpenApiResponse(description="유효하지 않은 tag_type입니다."),
    },
)
