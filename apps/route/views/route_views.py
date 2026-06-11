from typing import Any, cast

from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminRole
from apps.route.exceptions import RouteAlreadyLiked, RouteForbidden, RouteLikeNotFound, RouteNotFound
from apps.route.schemas.route_schemas import (
    admin_route_delete_schema,
    route_create_schema,
    route_delete_schema,
    route_like_schema,
    route_list_schema,
    route_unlike_schema,
    route_update_schema,
    user_liked_routes_schema,
    user_route_list_schema,
)
from apps.route.serializers.route_serializers import (
    RouteCreateResponseSerializer,
    RouteCreateSerializer,
    RouteLikeResponseSerializer,
    RouteListSerializer,
    RouteMyListSerializer,
    RouteUpdateResponseSerializer,
    RouteUpdateSerializer,
)
from apps.route.services.route_services import (
    admin_delete_route,
    create_route,
    delete_route,
    get_liked_routes,
    get_routes,
    get_user_routes,
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
        return Response(RouteCreateResponseSerializer(route).data, status=status.HTTP_201_CREATED)


class RouteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @route_update_schema
    def patch(self, request: Request, route_id: int) -> Response:
        serializer = RouteUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            route = update_route(cast(User, request.user), route_id, dict(serializer.validated_data))
        except RouteNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except RouteForbidden:
            return Response(
                {"error_detail": "본인이 작성한 경로만 수정할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN
            )
        return Response(RouteUpdateResponseSerializer(route).data)

    @route_delete_schema
    def delete(self, request: Request, route_id: int) -> Response:
        try:
            delete_route(cast(User, request.user), route_id)
        except RouteNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except RouteForbidden:
            return Response(
                {"error_detail": "본인이 작성한 경로만 삭제할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserRouteListView(APIView):
    permission_classes = [IsAuthenticated]

    @user_route_list_schema
    def get(self, request: Request, nickname: str) -> Response:
        try:
            page, paginator = get_user_routes(nickname, request)
        except RouteNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        serializer = RouteMyListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data)


class RouteLikeView(APIView):
    permission_classes = [IsAuthenticated]

    @route_like_schema
    def post(self, request: Request, route_id: int) -> Response:
        try:
            like = like_route(cast(User, request.user), route_id)
        except RouteNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except RouteAlreadyLiked as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_409_CONFLICT)
        data: dict[str, Any] = {
            "message": "좋아요가 추가되었습니다.",
            "like_id": like.id,
            "like_count": like.route.like_count,
        }
        return Response(RouteLikeResponseSerializer(data).data, status=status.HTTP_201_CREATED)

    @route_unlike_schema
    def delete(self, request: Request, route_id: int) -> Response:
        try:
            unlike_route(cast(User, request.user), route_id)
        except RouteNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except RouteLikeNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserLikedRoutesView(APIView):
    permission_classes = [IsAuthenticated]

    @user_liked_routes_schema
    def get(self, request: Request) -> Response:
        page, paginator = get_liked_routes(cast(User, request.user), request)
        serializer = RouteListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data)


class AdminRouteDetailView(APIView):
    permission_classes = [IsAdminRole]

    @admin_route_delete_schema
    def delete(self, request: Request, route_id: int) -> Response:
        try:
            admin_delete_route(route_id)
        except RouteNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
