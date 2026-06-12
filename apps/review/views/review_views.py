from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Avg, Count
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import AuthRequiredMixin
from apps.core.presigned_url.views import PresignedUrlView
from apps.review.schemas.review_schemas import (
    review_create_schema,
    review_delete_schema,
    review_image_presigned_url_schema,
    review_list_schema,
    review_update_schema,
)
from apps.review.serializers.review_serializers import (
    ReviewCreateResponseSerializer,
    ReviewCreateSerializer,
    ReviewListItemSerializer,
    ReviewUpdateResponseSerializer,
    ReviewUpdateSerializer,
)
from apps.review.services.review_services import (
    create_review,
    delete_review,
    get_reviews,
    update_review,
)


class PlaceReviewListCreateView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    @review_list_schema
    def get(self, request: Request, place_id: int) -> Response:
        reviews = get_reviews(place_id)
        agg = reviews.aggregate(avg=Avg("rating"), count=Count("id"))
        avg = agg["avg"]
        avg_rating = round(float(avg), 1) if avg is not None else 0.0
        count: int = agg["count"] or 0

        try:
            page_size = max(1, int(request.query_params.get("page_size", 4)))
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page_size, page = 4, 1

        offset = (page - 1) * page_size
        serializer = ReviewListItemSerializer(
            reviews[offset : offset + page_size],
            many=True,
            context={"request": request},
        )
        return Response({"count": count, "avg_rating": avg_rating, "results": serializer.data})

    @review_create_schema
    def post(self, request: Request, place_id: int) -> Response:
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        assert isinstance(user, AbstractBaseUser)
        data = serializer.validated_data
        review = create_review(
            user=user,
            place_id=place_id,
            rating=data["rating"],
            content=data["content"],
            image_url=data.get("image_url"),
        )
        return Response(
            ReviewCreateResponseSerializer(review, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ReviewDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @review_update_schema
    def patch(self, request: Request, review_id: int) -> Response:
        serializer = ReviewUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        assert isinstance(user, AbstractBaseUser)
        review = update_review(user=user, review_id=review_id, data=serializer.validated_data)
        return Response(ReviewUpdateResponseSerializer(review, context={"request": request}).data)

    @review_delete_schema
    def delete(self, request: Request, review_id: int) -> Response:
        user = request.user
        assert isinstance(user, AbstractBaseUser)
        delete_review(user=user, review_id=review_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReviewImagePresignedUrlView(AuthRequiredMixin, PresignedUrlView):
    permission_classes = [IsAuthenticated]
    path = "reviews"

    @review_image_presigned_url_schema
    def post(self, request: Request) -> Response:
        return self.handle_request(request)
