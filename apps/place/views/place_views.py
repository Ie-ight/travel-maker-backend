from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.place.models import Place
from apps.place.schemas.place_schemas import (
    place_detail_schema,
    place_filter_schema,
    place_list_schema,
    place_search_schema,
)
from apps.place.serializers.place_serializers import (
    PlaceDetailSerializer,
    PlaceListSerializer,
)
from apps.place.services.place_services import (
    get_place_detail,
    get_place_list,
    get_place_list_recommend,
    increment_view_count,
)


class CustomPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 100


class PlaceListView(APIView):
    permission_classes = [AllowAny]

    @place_list_schema
    def get(self, request: Request) -> Response:
        user_id = request.user.id if request.user.is_authenticated else None
        queryset = get_place_list(user_id=user_id)
        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, self.request)
        serializer = PlaceListSerializer(page, many=True, context={"request": self.request})
        return paginator.get_paginated_response(serializer.data)


class PlaceSearchView(APIView):
    permission_classes = [AllowAny]

    @place_search_schema
    def get(self, request: Request) -> Response:
        keyword = request.query_params.get("keyword", "").strip()
        sort = request.query_params.get("sort", "bookmark")
        order = request.query_params.get("order", "desc")
        user_id = request.user.id if request.user.is_authenticated else None

        if sort == "recommend":
            data = get_place_list_recommend(user_id=user_id, keyword=keyword)
        else:
            data = get_place_list(keyword=keyword, sort=sort, order=order, user_id=user_id)  # type: ignore[assignment]
        paginator = CustomPagination()
        page: list[Place] | None = paginator.paginate_queryset(data, self.request)  # type: ignore[arg-type]
        serializer = PlaceListSerializer(page, many=True, context={"request": self.request})
        return paginator.get_paginated_response(serializer.data)


class PlaceFilterView(APIView):
    permission_classes = [AllowAny]

    @place_filter_schema
    def get(self, request: Request) -> Response:
        keyword = request.query_params.get("keyword", "").strip()
        sort = request.query_params.get("sort", "bookmark")
        order = request.query_params.get("order", "desc")
        # tags=1&tags=3 (반복) 및 tags=1,3 (콤마) 모두 허용, 숫자가 아니면 무시
        tag_ids = [
            int(part)
            for raw in request.query_params.getlist("tags")
            for part in raw.split(",")
            if part.strip().isdigit()
        ]

        user_id = request.user.id if request.user.is_authenticated else None

        if sort == "recommend":
            data = get_place_list_recommend(user_id=user_id, keyword=keyword, tags=tag_ids or None)
        else:
            data = get_place_list(keyword=keyword, sort=sort, order=order, tags=tag_ids, user_id=user_id)  # type: ignore[assignment]
        paginator = CustomPagination()
        page: list[Place] | None = paginator.paginate_queryset(data, self.request)  # type: ignore[arg-type]
        serializer = PlaceListSerializer(page, many=True, context={"request": self.request})
        return paginator.get_paginated_response(serializer.data)


class PlaceDetailView(APIView):
    permission_classes = [AllowAny]

    @place_detail_schema
    def get(self, request: Request, place_id: int) -> Response:
        user_id = request.user.id if request.user.is_authenticated else None
        place = get_place_detail(place_id, user_id=user_id)
        if place is None:
            raise NotFound("존재하지 않는 장소입니다.")
        increment_view_count(place_id)
        return Response(PlaceDetailSerializer(place).data)
