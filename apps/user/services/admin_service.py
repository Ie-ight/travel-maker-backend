from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

from apps.user.models import User


class AdminUserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminUserService:
    @staticmethod
    def get_users(request: Request) -> tuple[QuerySet[User] | None, AdminUserPagination]:
        qs = User.objects.order_by("-id")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(nickname__icontains=search) | qs.filter(email__icontains=search)

        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        paginator = AdminUserPagination()
        page = paginator.paginate_queryset(qs, request)
        return page, paginator
