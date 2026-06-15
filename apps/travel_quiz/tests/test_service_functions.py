"""
make_description / build_type_tags / build_detail_cards 순수 함수 단위 테스트.

agents.md의 d1~d4 문구 및 card1~4 표와 코드 출력이 1:1로 일치하는지
전체 분기를 파라미터라이즈드 케이스로 고정한다. DB 접근 없음.
"""

import itertools

import pytest

from apps.travel_quiz.services.travel_quiz_services import (
    build_detail_cards,
    build_type_tags,
    calculate_accuracy,
    find_compatible_types,
    label_vector,
    make_description,
)
from apps.travel_quiz.tests.factories import TravelTypeFactory

ALL_TYPE_KEYS = ["".join(combo) for combo in itertools.product("tf", repeat=3)]

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_T = 0.7  # ≥ 0.5 → True 분기
_F = 0.3  # < 0.5  → False 분기


def _norm(active: bool, planned: bool, solo: bool, nature: bool, cultural: bool, budget: bool) -> list[float]:
    return [_T if v else _F for v in (active, planned, solo, nature, cultural, budget)]


# ---------------------------------------------------------------------------
# build_type_tags — 8 type_key 전수
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_key,expected",
    [
        ("ttt", ["액티비티형", "혼자형", "자연형"]),
        ("ttf", ["액티비티형", "혼자형", "도시형"]),
        ("tft", ["액티비티형", "단체형", "자연형"]),
        ("tff", ["액티비티형", "단체형", "도시형"]),
        ("ftt", ["힐링형", "혼자형", "자연형"]),
        ("ftf", ["힐링형", "혼자형", "도시형"]),
        ("fft", ["힐링형", "단체형", "자연형"]),
        ("fff", ["힐링형", "단체형", "도시형"]),
    ],
)
def test_build_type_tags(type_key: str, expected: list[str]) -> None:
    assert build_type_tags(type_key) == expected


# ---------------------------------------------------------------------------
# make_description — d1(2) × d2(4) × d3(2) × d4(4) 전 분기 커버 (8 케이스)
# ---------------------------------------------------------------------------

_D1_ACTIVE = "체력을 아낌없이 쓰는 활동형 여행자예요."
_D1_HEALING = "천천히 스며드는 여행을 좋아하는 힐링형 여행자예요."

_D2 = {
    (True, True): "철저한 준비로 혼자만의 루트를 만들며",
    (False, True): "계획 없이도 혼자 유연하게 움직이는 걸 즐기며",
    (True, False): "철저한 준비로 일행 모두의 동선을 짜며",
    (False, False): "즉흥적인 선택으로 함께하는 우연을 사랑하며",
}

_D3_NATURE = "자연 속에서 에너지를 충전하는 타입이에요."
_D3_CITY = "도시의 문화와 에너지에서 영감을 받는 타입이에요."

_D4 = {
    (True, True): "현지 문화를 가성비 있게 깊이 파고드는 걸 즐겨요.",
    (True, False): "그 지역의 이야기와 역사에 아낌없이 투자해요.",
    (False, True): "직접 체험하는 여행을 합리적인 가격에 즐겨요.",
    (False, False): "특별한 체험을 위해서라면 지갑 열기를 주저 않아요.",
}


def _expected_desc(active: bool, planned: bool, solo: bool, nature: bool, cultural: bool, budget: bool) -> str:
    d1 = _D1_ACTIVE if active else _D1_HEALING
    d2 = _D2[(planned, solo)]
    d3 = _D3_NATURE if nature else _D3_CITY
    d4 = _D4[(cultural, budget)]
    return f"{d1} {d2} {d3} {d4}"


@pytest.mark.parametrize(
    "active,planned,solo,nature,cultural,budget",
    [
        # d2=(T,T) d4=(T,T)
        (True, True, True, True, True, True),
        # d2=(F,T) d4=(T,F)  — d1/d3 반전
        (False, False, True, False, True, False),
        # d2=(T,F) d4=(F,T)
        (True, True, False, True, False, True),
        # d2=(F,F) d4=(F,F)  — d1/d3 반전
        (False, False, False, False, False, False),
        # d2=(T,T) d4=(F,T)  — d1/d3 반전
        (False, True, True, False, False, True),
        # d2=(F,T) d4=(F,F)
        (True, False, True, True, False, False),
        # d2=(T,F) d4=(T,F)  — d1/d3 반전
        (False, True, False, False, True, False),
        # d2=(F,F) d4=(T,T)
        (True, False, False, True, True, True),
    ],
)
def test_make_description(active: bool, planned: bool, solo: bool, nature: bool, cultural: bool, budget: bool) -> None:
    norm = _norm(active, planned, solo, nature, cultural, budget)
    assert make_description(norm) == _expected_desc(active, planned, solo, nature, cultural, budget)


# ---------------------------------------------------------------------------
# _build_detail_cards — card1~4 전 분기 커버 (동일 8 케이스)
# ---------------------------------------------------------------------------

_CARD1 = {
    True: ("몸으로 떠나는 여행", "체력을 아낌없이 쓰는 게 진짜 여행이에요."),
    False: ("천천히 스며드는 여행", "여유롭게 흡수하는 것이 나만의 여행법이에요."),
}

_CARD2 = {
    (True, True): ("나만의 완벽한 루트", "철저한 준비로 혼자만의 동선을 완성해요."),
    (False, True): ("즉흥적인 이동", "계획 없이 끌리는 골목으로 자유롭게 떠나요."),
    (True, False): ("완벽한 단체 동선", "철저한 준비로 일행 모두의 여행을 완성해요."),
    (False, False): ("함께하는 우연", "즉흥적인 선택으로 함께 만드는 특별한 순간이에요."),
}

_CARD3 = {
    True: ("자연 속 충전", "자연 속에서 에너지를 회복하는 타입이에요."),
    False: ("도시의 분위기", "도시의 빛과 문화에서 영감을 받아요."),
}

_CARD4 = {
    (True, True): ("알뜰한 문화 탐방", "현지 문화를 가성비 있게 깊이 파고들어요."),
    (True, False): ("문화에 아낌없이", "그 지역의 이야기와 역사에 아낌없이 투자해요."),
    (False, True): ("합리적인 체험", "직접 체험하는 여행을 합리적인 가격에 즐겨요."),
    (False, False): ("특별한 경험엔 아낌없이", "기억에 남을 순간엔 지갑을 열어요."),
}


def _expected_cards(
    active: bool, planned: bool, solo: bool, nature: bool, cultural: bool, budget: bool
) -> list[tuple[str, str]]:
    return [_CARD1[active], _CARD2[(planned, solo)], _CARD3[nature], _CARD4[(cultural, budget)]]


@pytest.mark.parametrize(
    "active,planned,solo,nature,cultural,budget",
    [
        (True, True, True, True, True, True),
        (False, False, True, False, True, False),
        (True, True, False, True, False, True),
        (False, False, False, False, False, False),
        (False, True, True, False, False, True),
        (True, False, True, True, False, False),
        (False, True, False, False, True, False),
        (True, False, False, True, True, True),
    ],
)
def test_build_detail_cards(
    active: bool, planned: bool, solo: bool, nature: bool, cultural: bool, budget: bool
) -> None:
    norm = _norm(active, planned, solo, nature, cultural, budget)
    actual = [(c.title, c.description) for c in build_detail_cards(norm)]
    assert actual == _expected_cards(active, planned, solo, nature, cultural, budget)


# ---------------------------------------------------------------------------
# label_vector — 6축 라벨링 + 백분율 변환
# ---------------------------------------------------------------------------


def test_label_vector() -> None:
    values = [0.8, 0.7, 0.6, 0.3, 0.7, 0.4]

    result = label_vector(values)

    assert result == [
        {"label": "액티비티형", "value": 80},
        {"label": "계획형", "value": 70},
        {"label": "혼자형", "value": 60},
        {"label": "자연형", "value": 30},
        {"label": "문화형", "value": 70},
        {"label": "가성비형", "value": 40},
    ]


def test_label_vector_반올림() -> None:
    assert label_vector([0.123, 0.456, 0.789, 0.001, 0.999, 0.5]) == [
        {"label": "액티비티형", "value": 12},
        {"label": "계획형", "value": 46},
        {"label": "혼자형", "value": 79},
        {"label": "자연형", "value": 0},
        {"label": "문화형", "value": 100},
        {"label": "가성비형", "value": 50},
    ]


# ---------------------------------------------------------------------------
# calculate_accuracy — type_key 3축(0,2,3)의 0.5 대비 편차 평균
# ---------------------------------------------------------------------------


def test_calculate_accuracy_명세_예시() -> None:
    norm = [0.8, 1, 1, 1, 0.6, 1]

    assert calculate_accuracy(norm) == 87


def test_calculate_accuracy_중립값은_0() -> None:
    assert calculate_accuracy([0.5] * 6) == 0


def test_calculate_accuracy_극단값은_100() -> None:
    assert calculate_accuracy([1, 1, 1, 1, 1, 1]) == 100
    assert calculate_accuracy([0, 0, 0, 0, 0, 0]) == 100


# ---------------------------------------------------------------------------
# find_compatible_types — type_key 3축(0,2,3) 코사인 유사도 기반 호환/비호환 유형
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_find_compatible_types_가장_가깝고_가장_먼_유형을_반환() -> None:
    types = {key: TravelTypeFactory(type_key=key) for key in ALL_TYPE_KEYS}  # type: ignore[misc]
    # axes 0,2,3 = (0.9, 0.9, 0.1) → "ttf"(자기 자신) 제외 중 "ttt"(1,1,1)가 가장 가깝고 "fff"(0,0,0)가 가장 멀다
    norm = [0.9, 0.5, 0.9, 0.1, 0.5, 0.5]

    compatible, incompatible = find_compatible_types(types["ttf"], norm)

    assert compatible.type_key == "ttt"
    assert incompatible.type_key == "fff"
    assert compatible.id != types["ttf"].id
    assert incompatible.id != types["ttf"].id
