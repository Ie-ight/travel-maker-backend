from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.route.serializers.route_serializers import (
    RouteCreateResponseSerializer,
    RouteCreateSerializer,
    RouteDetailSerializer,
    RouteLikeResponseSerializer,
    RouteListSerializer,
    RouteUpdateResponseSerializer,
    RouteUpdateSerializer,
)

route_create_schema = extend_schema(
    tags=["Route"],
    summary="경로 생성",
    description=(
        "여행 경로를 생성합니다. 시작일~종료일은 최대 4박 5일까지 설정할 수 있습니다.\n"
        "days는 일차별 방문 장소 목록으로, day_index는 1~5 사이의 일차 번호이고 "
        "place_ids는 해당 일차에 방문할 장소 ID를 1~5개까지 순서대로 담습니다.\n"
        "응답의 days에는 생성된 일차별 장소 정보(place_id, place_name, latitude, longitude, image_url)가 포함됩니다."
    ),
    request=RouteCreateSerializer,
    responses={201: RouteCreateResponseSerializer},
)

route_detail_schema = extend_schema(
    tags=["Route"],
    summary="경로 상세 조회",
    description=(
        "경로 상세 정보를 조회합니다. days는 day_index 오름차순으로, "
        "각 일차의 places는 방문 순서(order) 오름차순으로 정렬되어 내려옵니다.\n"
        "존재하지 않는 경로 ID면 404 에러가 발생합니다."
    ),
    responses={200: RouteDetailSerializer},
)

route_update_schema = extend_schema(
    tags=["Route"],
    summary="경로 수정 (본인만)",
    description=(
        "본인이 작성한 경로를 수정합니다. 모든 필드는 선택 입력이며 보낸 필드만 수정됩니다.\n"
        "days를 보내면 기존 일차/장소 목록은 모두 삭제되고 새로 보낸 내용으로 통째로 교체됩니다.\n"
        "존재하지 않는 경로 ID면 404, 본인이 작성한 경로가 아니면 403 에러가 발생합니다.\n"
        "응답의 days에는 수정 후 일차별 장소 정보(place_id, place_name, latitude, longitude, image_url)가 포함됩니다."
    ),
    request=RouteUpdateSerializer,
    responses={200: RouteUpdateResponseSerializer},
)

route_delete_schema = extend_schema(
    tags=["Route"],
    summary="경로 삭제 (본인만)",
    description=(
        "본인이 작성한 경로를 삭제합니다.\n"
        "존재하지 않는 경로 ID면 404, 본인이 작성한 경로가 아니면 403 에러가 발생합니다."
    ),
    responses={204: None},
)

route_list_schema = extend_schema(
    tags=["Route"],
    summary="경로 목록 조회",
    description=(
        "경로 목록을 조회합니다. ordering은 latest(최신순, 기본값) 또는 popular(좋아요 많은 순)를 선택할 수 있고, "
        "region_tag_id로 지역을, theme_tag_ids로 테마를 필터링할 수 있습니다."
    ),
    parameters=[
        OpenApiParameter(
            name="ordering", type=str, required=False, description="정렬: latest(최신순, 기본값) | popular(좋아요순)"
        ),
        OpenApiParameter(name="region_tag_id", type=int, required=False, description="지역 태그 ID로 필터링"),
        OpenApiParameter(
            name="theme_tag_ids",
            type=int,
            required=False,
            many=True,
            description="테마 태그 ID로 필터링 (여러 개 선택 시 모두 포함하는 경로만 조회)",
        ),
        OpenApiParameter(name="page", type=int, required=False, description="페이지 번호 (기본값 1)"),
        OpenApiParameter(name="page_size", type=int, required=False, description="페이지당 개수 (기본값 10, 최대 50)"),
    ],
    responses={200: RouteListSerializer(many=True)},
)

route_like_schema = extend_schema(
    tags=["Route"],
    summary="경로 좋아요 등록",
    description=(
        "해당 경로에 좋아요를 등록합니다.\n존재하지 않는 경로 ID면 404, 이미 좋아요한 경로면 409 에러가 발생합니다."
    ),
    responses={201: RouteLikeResponseSerializer},
)

route_unlike_schema = extend_schema(
    tags=["Route"],
    summary="경로 좋아요 취소",
    description=(
        "해당 경로에 등록했던 좋아요를 취소합니다.\n경로가 존재하지 않거나 좋아요한 적이 없으면 404 에러가 발생합니다."
    ),
    responses={204: None},
)

admin_route_delete_schema = extend_schema(
    tags=["Admin"],
    summary="경로 강제 삭제 (관리자)",
    description=(
        "관리자 권한으로 경로를 강제 삭제합니다. 작성자 본인이 아니어도 삭제할 수 있습니다.\n"
        "관리자가 아니면 403, 존재하지 않는 경로 ID면 404 에러가 발생합니다."
    ),
    responses={204: None},
)
