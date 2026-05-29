from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.place.serializers.place_serializers import (
    PlaceErrorResponseSerializer,
    PlaceListResponseSerializer,
    PlaceListSerializer,
)
from apps.place.services.place_services import get_place_list


class CustomPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 100


class PlaceListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Place"],
        parameters=[
            OpenApiParameter(name="page", type=int, description="페이지 번호: 0보다 작으면 1로 설정"),
            OpenApiParameter(name="page_size", type=int, description="목록 출력 개수"),
        ],
        responses={200: PlaceListResponseSerializer, 404: PlaceErrorResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        queryset = get_place_list()
        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, self.request)
        serializer = PlaceListSerializer(page, many=True, context={"request": self.request})
        return paginator.get_paginated_response(serializer.data)


class PlaceSearchView(PlaceListView): ...


class PlaceDetailView(APIView): ...
