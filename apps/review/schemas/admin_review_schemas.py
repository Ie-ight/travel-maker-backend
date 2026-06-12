from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.review.serializers.admin_review_serializers import AdminReviewListSerializer

admin_review_list_schema = extend_schema(
    tags=["Admin"],
    summary="리뷰 목록 조회 (관리자)",
    description="전체 리뷰 목록을 조회합니다. place_id, user_id로 필터링할 수 있습니다.",
    parameters=[
        OpenApiParameter(name="place_id", type=int, required=False, description="장소 ID 필터"),
        OpenApiParameter(name="user_id", type=int, required=False, description="유저 ID 필터"),
        OpenApiParameter(name="page", type=int, required=False, description="페이지 번호"),
    ],
    responses={200: AdminReviewListSerializer(many=True)},
)

admin_review_delete_schema = extend_schema(
    tags=["Admin"],
    summary="리뷰 강제 삭제 (관리자)",
    description="관리자 권한으로 리뷰를 강제 삭제합니다.\n존재하지 않는 리뷰면 404 에러가 발생합니다.",
    responses={204: None},
)
