from django.conf import settings

from apps.place.models import Place
from apps.route.models import Route
from apps.share.exceptions import ContentNotFound
from apps.travel_quiz.models import UserTestResult


def generate_share_url(
    content_type: str,
    content_id: int | None = None,
    type_key: str | None = None,
    vector: list[float] | None = None,
) -> str:
    frontend_url = settings.FRONTEND_URL

    if content_type == "place":
        return _place_share_url(frontend_url, content_id)  # type: ignore[arg-type]
    elif content_type == "route":
        return _route_share_url(frontend_url, content_id)  # type: ignore[arg-type]
    else:
        return _travel_quiz_share_url(frontend_url, content_id, type_key, vector)


def _place_share_url(frontend_url: str, place_id: int) -> str:
    if not Place.objects.filter(pk=place_id, is_active=True).exists():
        raise ContentNotFound("장소를 찾을 수 없습니다.")
    return f"{frontend_url}/place/{place_id}"


def _route_share_url(frontend_url: str, route_id: int) -> str:
    if not Route.objects.filter(pk=route_id).exists():
        raise ContentNotFound("경로를 찾을 수 없습니다.")
    return f"{frontend_url}/route/{route_id}"


def _travel_quiz_share_url(
    frontend_url: str,
    user_id: int | None,
    type_key: str | None,
    vector: list[float] | None,
) -> str:
    if user_id is not None:
        # 로그인 유저: DB에서 결과 조회
        try:
            result = UserTestResult.objects.select_related("travel_type").get(user_id=user_id)
        except UserTestResult.DoesNotExist:
            raise ContentNotFound("해당 유저의 테스트 결과를 찾을 수 없습니다.") from None
        type_key = result.travel_type.type_key
        vector_str = ",".join(str(round(float(v), 6)) for v in result.result_vector)
    else:
        # 비로그인 유저: 프론트에서 직접 넘긴 값 사용
        vector_str = ",".join(str(round(v, 6)) for v in vector)  # type: ignore[union-attr]

    return f"{frontend_url}/quiz/result?type_key={type_key}&vector={vector_str}"
