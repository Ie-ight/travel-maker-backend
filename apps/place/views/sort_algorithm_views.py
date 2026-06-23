from django.db.models import Count
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookmark.models import Bookmark
from apps.place.models import Place
from apps.place.schemas.sort_algorithm_schemas import place_recommend_schema
from apps.place.serializers.place_serializers import PlaceListSerializer
from apps.place.serializers.sort_algorithm_serializers import RecommendQuerySerializer
from apps.place.services.sort_algorithm_service import get_places_sorted_by_vector, get_popular_places
from apps.travel_quiz.models import UserTestResult


class RecommendPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 100


class PlaceRecommendView(APIView):
    permission_classes = [AllowAny]

    @place_recommend_schema
    def get(self, request: Request) -> Response:
        query_serializer = RecommendQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        region_tag_id = query_serializer.validated_data["region_tag_id"]

        tag_ids = [
            int(part)
            for raw in request.query_params.getlist("tags")
            for part in raw.split(",")
            if part.strip().isdigit()
        ] or None

        vector_places: list[Place] = []

        if request.user.is_authenticated:
            try:
                result = UserTestResult.objects.get(user=request.user)
                user_vector = list(result.result_vector) if result.result_vector is not None else None
                if user_vector and len(user_vector) == 6:
                    vector_places = list(
                        get_places_sorted_by_vector(
                            user_vector,
                            tag_ids=tag_ids,
                            region_tag_id=region_tag_id,
                            limit=None,
                        )
                    )
            except UserTestResult.DoesNotExist:
                pass

        if vector_places:
            vector_ids = {p.id for p in vector_places}
            remaining_qs = (
                Place.objects.filter(is_active=True)
                .exclude(id__in=vector_ids)
                .annotate(bookmark_count=Count("bookmarks", distinct=True))
                .prefetch_related("images", "tags")
                .order_by("-bookmark_count", "-rating_avg", "-view_count")
            )
            if tag_ids:
                for tag_id in tag_ids:
                    remaining_qs = remaining_qs.filter(tags__id=tag_id)
            if region_tag_id:
                remaining_qs = remaining_qs.filter(tags__id=region_tag_id)
            places: list[Place] = vector_places + list(remaining_qs)
        else:
            places = list(get_popular_places(tag_ids=tag_ids, region_tag_id=region_tag_id, limit=None))

        paginator = RecommendPagination()
        page: list[Place] | None = paginator.paginate_queryset(places, request)  # type: ignore[arg-type]

        if request.user.is_authenticated and page:
            bookmarked_ids = set(
                Bookmark.objects.filter(
                    user_id=request.user.pk,
                    place_id__in=[p.id for p in page],
                ).values_list("place_id", flat=True)
            )
            for place in page:
                place.is_bookmarked = place.id in bookmarked_ids  # type: ignore[attr-defined]
        else:
            for place in page or []:
                place.is_bookmarked = False  # type: ignore[attr-defined]

        serializer = PlaceListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
