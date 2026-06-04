import urllib.error

from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.place.models import Place
from apps.place.schemas.map_api_schemas import place_map_schema, place_route_schema
from apps.place.serializers.map_api_serializer import PlaceMapSerializer
from apps.place.services.map_api_service import get_places_for_map, get_route


class PlaceMapView(APIView):
    permission_classes = [AllowAny]

    @place_map_schema
    def get(self, request: Request) -> Response:
        places = get_places_for_map()
        serializer = PlaceMapSerializer(places, many=True)
        return Response(serializer.data)


class PlaceRouteView(APIView):
    permission_classes = [AllowAny]

    @place_route_schema
    def get(self, request: Request) -> Response:
        try:
            origin_lat = float(request.query_params["origin_lat"])
            origin_lng = float(request.query_params["origin_lng"])
            place_id = int(request.query_params["place_id"])
        except (KeyError, ValueError):
            return Response({"error_detail": "origin_lat, origin_lng, place_id 파라미터가 필요합니다."}, status=400)

        place = Place.objects.filter(id=place_id).only("latitude", "longitude").first()
        if place is None:
            return Response({"error_detail": "존재하지 않는 장소입니다."}, status=404)

        try:
            data = get_route(origin_lat, origin_lng, float(place.latitude), float(place.longitude))
        except ValueError as e:
            return Response({"error_detail": str(e)}, status=500)
        except urllib.error.HTTPError as e:
            return Response({"error_detail": f"Kakao Mobility API 오류: {e.code}"}, status=502)
        except urllib.error.URLError:
            return Response({"error_detail": "Kakao Mobility API 연결 실패"}, status=502)

        return Response(data)
