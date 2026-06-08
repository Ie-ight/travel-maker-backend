from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminRole
from apps.review.exceptions import ReviewNotFound
from apps.review.schemas.admin_review_schemas import admin_review_delete_schema, admin_review_list_schema
from apps.review.serializers.admin_review_serializers import AdminReviewListSerializer
from apps.review.services.admin_review_service import admin_delete_review, get_admin_reviews


class AdminReviewListView(APIView):
    permission_classes = [IsAdminRole]

    @admin_review_list_schema
    def get(self, request: Request) -> Response:
        page, paginator = get_admin_reviews(request)
        serializer = AdminReviewListSerializer(page, many=True)
        return Response(paginator.get_paginated_response(serializer.data).data)


class AdminReviewDetailView(APIView):
    permission_classes = [IsAdminRole]

    @admin_review_delete_schema
    def delete(self, request: Request, review_id: int) -> Response:
        try:
            admin_delete_review(review_id)
        except ReviewNotFound as e:
            return Response({"error_detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
