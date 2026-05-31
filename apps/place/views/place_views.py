from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.place.serializers.place_serializers import (
    PlaceDetailSerializer,
    PlaceErrorResponseSerializer,
    PlaceListResponseSerializer,
    PlaceListSerializer,
)
from apps.place.services.place_services import get_place_detail, get_place_list


class CustomPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 100


class PlaceListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Place"],
        parameters=[
            OpenApiParameter(name="page", type=int, description="페이지 번호: 0보다 작거나 없는 페이지는 404"),
            OpenApiParameter(name="page_size", type=int, description="목록 출력 개수: 기본 8, 최대 100"),
        ],
        responses={200: PlaceListResponseSerializer, 404: PlaceErrorResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        queryset = get_place_list()
        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, self.request)
        serializer = PlaceListSerializer(page, many=True, context={"request": self.request})
        return paginator.get_paginated_response(serializer.data)


class PlaceSearchView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
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
    def get(self, request: Request) -> Response:
        keyword = request.query_params.get("keyword", "").strip()
        sort = request.query_params.get("sort", "bookmark")
        order = request.query_params.get("order", "desc")

        queryset = get_place_list(keyword=keyword, sort=sort, order=order)
        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, self.request)
        serializer = PlaceListSerializer(page, many=True, context={"request": self.request})
        return paginator.get_paginated_response(serializer.data)


class PlaceDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Place"],
        responses={200: PlaceDetailSerializer, 404: PlaceErrorResponseSerializer},
    )
    def get(self, request: Request, place_id: int) -> Response:
        place = get_place_detail(place_id)
        if place is None:
            raise NotFound("존재하지 않는 장소입니다.")
        return Response(PlaceDetailSerializer(place).data)
