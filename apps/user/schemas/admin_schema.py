from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,  # type: ignore[attr-defined]
    extend_schema,
)

from apps.user.serializers.admin_serializers import AdminUserListSerializer

admin_user_list_schema = extend_schema(
    summary="회원 목록 조회 (관리자)",
    parameters=[
        OpenApiParameter(name="search", type=OpenApiTypes.STR, required=False, description="닉네임·이메일 검색"),
        OpenApiParameter(name="is_active", type=OpenApiTypes.BOOL, required=False, description="활성 여부 필터"),
        OpenApiParameter(name="page", type=OpenApiTypes.INT, required=False, description="페이지 번호"),
    ],
    responses={200: AdminUserListSerializer(many=True)},
)
