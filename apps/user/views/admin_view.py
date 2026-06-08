from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminRole
from apps.user.schemas.admin_schema import admin_user_list_schema
from apps.user.serializers.admin_serializers import AdminUserListSerializer
from apps.user.services.admin_service import AdminUserService


class AdminUserListView(APIView):
    permission_classes = [IsAdminRole]

    @admin_user_list_schema
    def get(self, request: Request) -> Response:
        page, paginator = AdminUserService.get_users(request)
        serializer = AdminUserListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data)
