from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.route.serializers.route_serializers import (
    RouteCreateResponseSerializer,
    RouteCreateSerializer,
    RouteLikeResponseSerializer,
    RouteListSerializer,
    RouteMyListSerializer,
    RouteUpdateResponseSerializer,
    RouteUpdateSerializer,
)

route_create_schema = extend_schema(
    tags=["Route"],
    summary="경로 생성",
    request=RouteCreateSerializer,
    responses={201: RouteCreateResponseSerializer},
)

route_update_schema = extend_schema(
    tags=["Route"],
    summary="경로 수정 (본인만)",
    request=RouteUpdateSerializer,
    responses={200: RouteUpdateResponseSerializer},
)

route_delete_schema = extend_schema(
    tags=["Route"],
    summary="경로 삭제 (본인만)",
    responses={204: None},
)

route_list_schema = extend_schema(
    tags=["Route"],
    summary="경로 목록 조회",
    parameters=[
        OpenApiParameter(name="ordering", type=str, required=False, description="정렬 (latest | popular)"),
        OpenApiParameter(name="region_tag_id", type=int, required=False, description="지역 태그 ID"),
        OpenApiParameter(name="theme_tag_ids", type=int, required=False, many=True, description="테마 태그 ID"),
        OpenApiParameter(name="page", type=int, required=False),
        OpenApiParameter(name="page_size", type=int, required=False),
    ],
    responses={200: RouteListSerializer(many=True)},
)

user_route_list_schema = extend_schema(
    tags=["Route"],
    summary="마이페이지 경로 조회",
    parameters=[
        OpenApiParameter(name="page", type=int, required=False),
    ],
    responses={200: RouteMyListSerializer(many=True)},
)

route_like_schema = extend_schema(
    tags=["Route"],
    summary="경로 좋아요 등록",
    responses={201: RouteLikeResponseSerializer},
)

route_unlike_schema = extend_schema(
    tags=["Route"],
    summary="경로 좋아요 취소",
    responses={204: None},
)

user_liked_routes_schema = extend_schema(
    tags=["Route"],
    summary="내가 좋아요한 경로 목록",
    parameters=[
        OpenApiParameter(name="page", type=int, required=False),
    ],
    responses={200: RouteListSerializer(many=True)},
)

admin_route_delete_schema = extend_schema(
    tags=["Admin"],
    summary="경로 강제 삭제 (관리자)",
    responses={204: None},
)
