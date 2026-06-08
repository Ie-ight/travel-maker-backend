from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,  # type: ignore[attr-defined]
    extend_schema,
)

from apps.review.serializers.admin_review_serializers import AdminReviewListSerializer

admin_review_list_schema = extend_schema(
    tags=["Admin"],
    summary="리뷰 목록 조회 (관리자)",
    parameters=[
        OpenApiParameter(name="place_id", type=OpenApiTypes.INT, required=False, description="장소 ID 필터"),
        OpenApiParameter(name="user_id", type=OpenApiTypes.INT, required=False, description="유저 ID 필터"),
        OpenApiParameter(name="page", type=OpenApiTypes.INT, required=False, description="페이지 번호"),
    ],
    responses={200: AdminReviewListSerializer(many=True)},
)

admin_review_delete_schema = extend_schema(
    tags=["Admin"],
    summary="리뷰 강제 삭제 (관리자)",
    responses={204: None},
)
