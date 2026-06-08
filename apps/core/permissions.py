from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.user.models import User


class IsAdminRole(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, User)
            and request.user.role == User.Role.ADMIN
        )
