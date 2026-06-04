import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.db.models import QuerySet

from apps.place.models import Place


def get_places_for_map() -> QuerySet[Place]:
    return Place.objects.prefetch_related("images").only("id", "place_name", "latitude", "longitude", "rating_avg")


def get_route(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> dict:
    """
    Kakao Mobility Directions API 호출 (자동차 경로).
    REST_API_KEY 필요: settings.KAKAO_REST_API_KEY
    """
    rest_api_key = getattr(settings, "KAKAO_REST_API_KEY", None)
    if not rest_api_key:
        raise ValueError("KAKAO_REST_API_KEY가 설정되지 않았습니다.")

    params = urllib.parse.urlencode(
        {
            "origin": f"{origin_lng},{origin_lat}",
            "destination": f"{dest_lng},{dest_lat}",
        }
    )
    url = f"https://apis-navi.kakaomobility.com/v1/directions?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {rest_api_key}"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise urllib.error.HTTPError(e.url, e.code, e.msg, e.hdrs, e.fp) from e
