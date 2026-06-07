from dataclasses import dataclass
from typing import cast

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import transaction
from pgvector.django import CosineDistance

from apps.place.models import Place
from apps.travel_quiz.models import TravelType, UserTestResult
from apps.travel_quiz.services.quiz_data import QUIZ_DATA

_PLAN_SOLO_DESCRIPTIONS = {
    (True, True): "철저한 준비로 혼자만의 루트를 만들며",
    (False, True): "계획 없이도 혼자 유연하게 움직이는 걸 즐기며",
    (True, False): "철저한 준비로 일행 모두의 동선을 짜며",
    (False, False): "즉흥적인 선택으로 함께하는 우연을 사랑하며",
}

_EXPERIENCE_BUDGET_DESCRIPTIONS = {
    (True, True): "현지 문화를 가성비 있게 깊이 파고드는 걸 즐겨요.",
    (True, False): "그 지역의 이야기와 역사에 아낌없이 투자해요.",
    (False, True): "직접 체험하는 여행을 합리적인 가격에 즐겨요.",
    (False, False): "특별한 체험을 위해서라면 지갑 열기를 주저 않아요.",
}


@dataclass
class QuizSubmitResult:
    saved: bool
    travel_type: TravelType
    dynamic_description: str
    result_vector: list[float]
    recommended_places: list[Place]


def _calculate_norm_vector(answers: list[str]) -> list[float]:
    scores = [0] * 6
    for answer, question in zip(answers, QUIZ_DATA, strict=True):
        weights = cast(list[int], question[answer.lower()]["weights"])
        for i, weight in enumerate(weights):
            scores[i] += weight
    return [max(0.0, min(1.0, (score + 5) / 10)) for score in scores]


def _determine_type_key(norm: list[float]) -> str:
    is_active = norm[0] >= 0.5  # activity
    is_solo = norm[2] >= 0.5  # social
    is_nature = norm[3] >= 0.5  # space
    return ("t" if is_active else "f") + ("t" if is_solo else "f") + ("t" if is_nature else "f")


def _make_dynamic_description(norm: list[float]) -> str:
    is_active = norm[0] >= 0.5
    is_planned = norm[1] >= 0.5
    is_solo = norm[2] >= 0.5
    is_nature = norm[3] >= 0.5
    is_cultural = norm[4] >= 0.5
    is_budget = norm[5] >= 0.5

    d1 = (
        "체력을 아낌없이 쓰는 활동형 여행자예요." if is_active else "천천히 스며드는 여행을 좋아하는 힐링형 여행자예요."
    )
    d2 = _PLAN_SOLO_DESCRIPTIONS[(is_planned, is_solo)]
    d3 = (
        "자연 속에서 에너지를 충전하는 타입이에요." if is_nature else "도시의 문화와 에너지에서 영감을 받는 타입이에요."
    )
    d4 = _EXPERIENCE_BUDGET_DESCRIPTIONS[(is_cultural, is_budget)]
    return f"{d1} {d2} {d3} {d4}"


def _get_recommended_places(result_vector: list[float]) -> list[Place]:
    return list(
        Place.objects.filter(is_active=True, place_feature__isnull=False)
        .annotate(distance=CosineDistance("place_feature__style_vector", result_vector))
        .select_related("place_feature")
        .prefetch_related("images", "tags")
        .order_by("distance")[:3]
    )


@transaction.atomic  # 점수 계산과 로그인 유저 자동저장 묶음
def submit_quiz(user: AbstractBaseUser | AnonymousUser, answers: list[str]) -> QuizSubmitResult:
    norm = _calculate_norm_vector(answers)
    type_key = _determine_type_key(norm)
    dynamic_description = _make_dynamic_description(norm)
    travel_type = TravelType.objects.prefetch_related("tags").get(type_key=type_key)

    saved = False
    if user.is_authenticated:
        UserTestResult.objects.update_or_create(
            user=user,
            defaults={"travel_type": travel_type, "result_vector": norm},
        )
        saved = True

    recommended_places = _get_recommended_places(norm)

    return QuizSubmitResult(
        saved=saved,
        travel_type=travel_type,
        dynamic_description=dynamic_description,
        result_vector=norm,
        recommended_places=recommended_places,
    )
