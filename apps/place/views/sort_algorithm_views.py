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
from apps.place.services.sort_algorithm_service import get_place_ids_sorted_by_vector, get_popular_places
from apps.travel_quiz.models import UserTestResult

_POPULAR_FALLBACK_LIMIT = 500


class RecommendPagination(PageNumberPagination):
    page_size = 12
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

        paginator = RecommendPagination()

        # 벡터 추천: ID 목록만 가져온 뒤 현재 페이지 ID에 해당하는 객체만 DB에서 로드
        # → 20,000개 정수(~160KB)만 메모리에 올림, Place 객체는 페이지당 8개만 로드
        ordered_ids: list[int] = []
        use_vector = False

        if request.user.is_authenticated:
            try:
                result = UserTestResult.objects.get(user=request.user)
                user_vector = list(result.result_vector) if result.result_vector is not None else None
                if user_vector and len(user_vector) == 6:
                    ordered_ids = get_place_ids_sorted_by_vector(
                        user_vector,
                        tag_ids=tag_ids,
                        region_tag_id=region_tag_id,
                    )
                    use_vector = True
            except UserTestResult.DoesNotExist:
                pass

        if use_vector:
            # ID 목록으로 페이지 슬라이싱 (정수만, 가벼움)
            page_ids: list[int] | None = paginator.paginate_queryset(ordered_ids, request)  # type: ignore[arg-type]
            if not page_ids:
                return paginator.get_paginated_response([])

            id_order = {pid: i for i, pid in enumerate(page_ids)}
            page_places: list[Place] = sorted(  # type: ignore[assignment]
                Place.objects.filter(id__in=page_ids)
                .annotate(bookmark_count=Count("bookmarks", distinct=True))
                .prefetch_related("images", "tags"),
                key=lambda p: id_order[p.id],
            )
        else:
            # 비로그인/퀴즈 미완료: 인기순 상위 _POPULAR_FALLBACK_LIMIT개
            popular = list(
                get_popular_places(tag_ids=tag_ids, region_tag_id=region_tag_id, limit=_POPULAR_FALLBACK_LIMIT)
            )
            page_places_raw: list[Place] | None = paginator.paginate_queryset(popular, request)  # type: ignore[arg-type]
            page_places = page_places_raw or []

        if request.user.is_authenticated and page_places:
            bookmarked_ids = set(
                Bookmark.objects.filter(
                    user_id=request.user.pk,
                    place_id__in=[p.id for p in page_places],
                ).values_list("place_id", flat=True)
            )
            for place in page_places:
                place.is_bookmarked = place.id in bookmarked_ids  # type: ignore[attr-defined]
        else:
            for place in page_places:
                place.is_bookmarked = False  # type: ignore[attr-defined]

        serializer = PlaceListSerializer(page_places, many=True)
        return paginator.get_paginated_response(serializer.data)
