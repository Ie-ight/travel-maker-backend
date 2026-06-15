import math
from dataclasses import dataclass
from typing import cast

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import transaction
from pgvector.django import CosineDistance

from apps.place.models import Place
from apps.travel_quiz.exceptions import InvalidTravelTypeId, QuizResultNotFound
from apps.travel_quiz.models import TravelType, UserTestResult
from apps.travel_quiz.services.quiz_data import QUIZ_DATA
from apps.user.models import User

_AXIS_TAG_LABELS: tuple[dict[str, str], ...] = (
    {"t": "액티비티형", "f": "힐링형"},
    {"t": "혼자형", "f": "단체형"},
    {"t": "자연형", "f": "도시형"},
)

# 6축 라벨 (순서: activity, plan, social, space, experience, budget)
_AXIS_LABELS: tuple[str, ...] = ("액티비티형", "계획형", "혼자형", "자연형", "문화형", "가성비형")

# type_key를 결정하는 3축의 인덱스 (_determine_type_key와 동일: activity, social, space)
_TYPE_KEY_AXES = (0, 2, 3)

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
class DetailCard:
    title: str
    description: str


_CARD1: dict[bool, DetailCard] = {
    True: DetailCard("몸으로 떠나는 여행", "체력을 아낌없이 쓰는 게 진짜 여행이에요."),
    False: DetailCard("천천히 스며드는 여행", "여유롭게 흡수하는 것이 나만의 여행법이에요."),
}

_CARD2: dict[tuple[bool, bool], DetailCard] = {
    (True, True): DetailCard("나만의 완벽한 루트", "철저한 준비로 혼자만의 동선을 완성해요."),
    (False, True): DetailCard("즉흥적인 이동", "계획 없이 끌리는 골목으로 자유롭게 떠나요."),
    (True, False): DetailCard("완벽한 단체 동선", "철저한 준비로 일행 모두의 여행을 완성해요."),
    (False, False): DetailCard("함께하는 우연", "즉흥적인 선택으로 함께 만드는 특별한 순간이에요."),
}

_CARD3: dict[bool, DetailCard] = {
    True: DetailCard("자연 속 충전", "자연 속에서 에너지를 회복하는 타입이에요."),
    False: DetailCard("도시의 분위기", "도시의 빛과 문화에서 영감을 받아요."),
}

_CARD4: dict[tuple[bool, bool], DetailCard] = {
    (True, True): DetailCard("알뜰한 문화 탐방", "현지 문화를 가성비 있게 깊이 파고들어요."),
    (True, False): DetailCard("문화에 아낌없이", "그 지역의 이야기와 역사에 아낌없이 투자해요."),
    (False, True): DetailCard("합리적인 체험", "직접 체험하는 여행을 합리적인 가격에 즐겨요."),
    (False, False): DetailCard("특별한 경험엔 아낌없이", "기억에 남을 순간엔 지갑을 열어요."),
}


@dataclass
class QuizSubmitResult:
    saved: bool
    travel_type: TravelType
    type_tags: list[str]
    description: str
    detail_cards: list[DetailCard]
    result_vector: list[float]
    accuracy: int
    recommended_places: list[Place]
    compatible_type: TravelType
    incompatible_type: TravelType


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


def build_type_tags(type_key: str) -> list[str]:
    return [labels[char] for labels, char in zip(_AXIS_TAG_LABELS, type_key, strict=True)]


def label_vector(values: list[float]) -> list[dict[str, object]]:
    return [{"label": label, "value": round(value * 100)} for label, value in zip(_AXIS_LABELS, values, strict=True)]


def calculate_match_rate(obj: Place) -> int:
    similarity = 1 - float(obj.distance)  # type: ignore[attr-defined]
    return round(max(0.0, min(1.0, similarity)) * 100)


def calculate_accuracy(norm: list[float]) -> int:
    deviations = [abs(norm[i] - 0.5) * 2 for i in _TYPE_KEY_AXES]
    return round(sum(deviations) / len(deviations) * 100)


def _type_axis_vector(type_key: str) -> list[float]:
    return [1.0 if ch == "t" else 0.0 for ch in type_key]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / denom if denom else 0.0


def find_compatible_types(travel_type: TravelType, norm: list[float]) -> tuple[TravelType, TravelType]:
    user_vec = [norm[i] for i in _TYPE_KEY_AXES]
    scored = [
        (other, _cosine_similarity(user_vec, _type_axis_vector(other.type_key)))
        for other in TravelType.objects.exclude(id=travel_type.id)
    ]
    compatible = max(scored, key=lambda pair: pair[1])[0]
    incompatible = min(scored, key=lambda pair: pair[1])[0]
    return compatible, incompatible


def make_description(norm: list[float]) -> str:
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


def build_detail_cards(norm: list[float]) -> list[DetailCard]:
    is_active = norm[0] >= 0.5
    is_planned = norm[1] >= 0.5
    is_solo = norm[2] >= 0.5
    is_nature = norm[3] >= 0.5
    is_cultural = norm[4] >= 0.5
    is_budget = norm[5] >= 0.5

    return [
        _CARD1[is_active],
        _CARD2[(is_planned, is_solo)],
        _CARD3[is_nature],
        _CARD4[(is_cultural, is_budget)],
    ]


def get_recommended_places(result_vector: list[float]) -> list[Place]:
    return list(
        Place.objects.filter(is_active=True, place_feature__isnull=False)
        .annotate(distance=CosineDistance("place_feature__style_vector", result_vector))
        .select_related("place_feature")
        .prefetch_related("images", "tags")
        .order_by("distance")[:3]
    )


@transaction.atomic  # 점수 계산과 로그인 유저 자동저장 로직 묶음
def submit_quiz(user: AbstractBaseUser | AnonymousUser, answers: list[str]) -> QuizSubmitResult:
    norm = _calculate_norm_vector(answers)
    type_key = _determine_type_key(norm)
    travel_type = TravelType.objects.get(type_key=type_key)

    saved = False
    if user.is_authenticated:
        UserTestResult.objects.update_or_create(
            user=user,
            defaults={"travel_type": travel_type, "result_vector": norm},
        )
        saved = True

    recommended_places = get_recommended_places(norm)
    compatible_type, incompatible_type = find_compatible_types(travel_type, norm)

    return QuizSubmitResult(
        saved=saved,
        travel_type=travel_type,
        type_tags=build_type_tags(type_key),
        description=make_description(norm),
        detail_cards=build_detail_cards(norm),
        result_vector=norm,
        accuracy=calculate_accuracy(norm),
        recommended_places=recommended_places,
        compatible_type=compatible_type,
        incompatible_type=incompatible_type,
    )


def get_user_quiz_result(user: User) -> UserTestResult:
    try:
        return UserTestResult.objects.select_related("travel_type").get(user=user)
    except UserTestResult.DoesNotExist:
        raise QuizResultNotFound() from None


def update_user_avatar(user: User, travel_type_id: int) -> bool:
    try:
        travel_type = TravelType.objects.get(id=travel_type_id)
    except TravelType.DoesNotExist:
        raise InvalidTravelTypeId() from None

    user.profile_img_url = travel_type.image_url
    user.save(update_fields=["profile_img_url"])
    return True
