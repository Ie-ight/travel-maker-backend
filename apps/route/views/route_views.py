from typing import cast

from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminRole
from apps.route.schemas.route_schemas import (
    admin_route_delete_schema,
    route_create_schema,
    route_delete_schema,
    route_detail_schema,
    route_like_schema,
    route_list_schema,
    route_unlike_schema,
    route_update_schema,
)
from apps.route.serializers.route_serializers import (
    RouteCreateResponseSerializer,
    RouteCreateSerializer,
    RouteDetailSerializer,
    RouteLikeResponseSerializer,
    RouteListSerializer,
    RouteUpdateResponseSerializer,
    RouteUpdateSerializer,
)
from apps.route.services.route_services import (
    admin_delete_route,
    create_route,
    delete_route,
    get_route_detail,
    get_routes,
    like_route,
    unlike_route,
    update_route,
)
from apps.user.models import User


class RouteListCreateView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    @route_list_schema
    def get(self, request: Request) -> Response:
        page, paginator = get_routes(request)
        serializer = RouteListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data)

    @route_create_schema
    def post(self, request: Request) -> Response:
        serializer = RouteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = create_route(cast(User, request.user), dict(serializer.validated_data))
        detail_route = get_route_detail(route.id)
        return Response(RouteCreateResponseSerializer(detail_route).data, status=status.HTTP_201_CREATED)


class RouteDetailView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    @route_detail_schema
    def get(self, request: Request, route_id: int) -> Response:
        route = get_route_detail(route_id)
        return Response(RouteDetailSerializer(route).data)

    @route_update_schema
    def patch(self, request: Request, route_id: int) -> Response:
        serializer = RouteUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = update_route(cast(User, request.user), route_id, dict(serializer.validated_data))
        detail_route = get_route_detail(route.id)
        return Response(RouteUpdateResponseSerializer(detail_route).data)

    @route_delete_schema
    def delete(self, request: Request, route_id: int) -> Response:
        delete_route(cast(User, request.user), route_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RouteLikeView(APIView):
    permission_classes = [IsAuthenticated]

    @route_like_schema
    def post(self, request: Request, route_id: int) -> Response:
        like = like_route(cast(User, request.user), route_id)
        data: dict[str, str | int] = {
            "message": "좋아요가 추가되었습니다.",
            "like_id": like.id,
            "like_count": like.route.like_count,
        }
        return Response(RouteLikeResponseSerializer(data).data, status=status.HTTP_201_CREATED)

    @route_unlike_schema
    def delete(self, request: Request, route_id: int) -> Response:
        unlike_route(cast(User, request.user), route_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRouteDetailView(APIView):
    permission_classes = [IsAdminRole]

    @admin_route_delete_schema
    def delete(self, request: Request, route_id: int) -> Response:
        admin_delete_route(route_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
