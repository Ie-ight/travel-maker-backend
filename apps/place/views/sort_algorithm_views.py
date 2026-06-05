from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.place.schemas.sort_algorithm_schemas import place_recommend_schema
from apps.place.serializers.place_serializers import PlaceListSerializer
from apps.place.serializers.sort_algorithm_serializers import RecommendQuerySerializer
from apps.place.services.sort_algorithm_service import get_places_sorted_by_vector, get_popular_places
from apps.travel_quiz.models import UserTestResult


class PlaceRecommendView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    @place_recommend_schema
    def get(self, request: Request) -> Response:
        query_serializer = RecommendQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        region_tag_id = query_serializer.validated_data["region_tag_id"]
        limit = query_serializer.validated_data["limit"]

        tag_ids = [
            int(part)
            for raw in request.query_params.getlist("tags")
            for part in raw.split(",")
            if part.strip().isdigit()
        ] or None

        places = None

        if request.user.is_authenticated:
            try:
                result = UserTestResult.objects.get(user=request.user)
                user_vector = list(result.result_vector)
                places = get_places_sorted_by_vector(
                    user_vector,
                    tag_ids=tag_ids,
                    region_tag_id=region_tag_id,
                    limit=limit,
                )
            except UserTestResult.DoesNotExist:
                pass

        if places is None:
            places = get_popular_places(
                tag_ids=tag_ids,
                region_tag_id=region_tag_id,
                limit=limit,
            )

        serializer = PlaceListSerializer(places, many=True)
        return Response(serializer.data)
