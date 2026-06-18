import itertools

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.place.models import PlaceFeature
from apps.travel_quiz.models import UserTestResult
from apps.travel_quiz.services.travel_quiz_services import build_type_tags
from apps.travel_quiz.tests.factories import PlaceFactory, TravelTypeFactory, UserFactory
from apps.user.models import User

ALL_TYPE_KEYS = ["".join(combo) for combo in itertools.product("tf", repeat=3)]
VALID_ANSWERS = ["A"] * 12


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def user() -> User:
    return UserFactory()  # type: ignore[return-value]


@pytest.fixture
def auth_client(client: APIClient, user: User) -> APIClient:
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def travel_types(db: None) -> dict[str, object]:
    # type_key는 응답값 계산 결과에 따라 결정되므로 8가지 조합을 모두 시드해 둔다
    return {key: TravelTypeFactory(type_key=key) for key in ALL_TYPE_KEYS}


@pytest.mark.django_db
class TestQuizSubmit:
    def test_게스트_제출_저장안됨(self, client: APIClient, travel_types: dict[str, object]) -> None:
        response = client.post("/api/v1/quiz/submit", {"answers": VALID_ANSWERS}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["saved"] is False
        assert UserTestResult.objects.count() == 0

    def test_로그인_유저_제출_자동저장및_재제출시_upsert(
        self, auth_client: APIClient, user: User, travel_types: dict[str, object]
    ) -> None:
        response = auth_client.post("/api/v1/quiz/submit", {"answers": VALID_ANSWERS}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["saved"] is True
        result = UserTestResult.objects.get(user=user)
        assert result.travel_type.type_key == response.data["type_key"]

        other_answers = ["B"] * 12
        response = auth_client.post("/api/v1/quiz/submit", {"answers": other_answers}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert UserTestResult.objects.filter(user=user).count() == 1
        assert UserTestResult.objects.get(user=user).travel_type.type_key == response.data["type_key"]

    def test_answers_길이가_12가_아니면_400(self, client: APIClient, travel_types: dict[str, object]) -> None:
        response = client.post("/api/v1/quiz/submit", {"answers": ["A"] * 11}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_detail"] == "answers 길이가 12여야 합니다."

    def test_answers_항목이_A_또는_B가_아니면_400(self, client: APIClient, travel_types: dict[str, object]) -> None:
        response = client.post("/api/v1/quiz/submit", {"answers": ["A"] * 11 + ["C"]}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_detail"] == "answers 각 항목은 'A' 또는 'B'여야 합니다."

    def test_추천_장소와_결과벡터_타입태그_상세카드_포함(
        self, client: APIClient, travel_types: dict[str, object]
    ) -> None:
        place = PlaceFactory()
        PlaceFeature.objects.create(place=place, style_vector=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

        response = client.post("/api/v1/quiz/submit", {"answers": VALID_ANSWERS}, format="json")

        assert response.status_code == status.HTTP_200_OK

        result_vector = response.data["result_vector"]
        assert len(result_vector) == 6
        for axis in result_vector:
            assert axis.keys() == {"label", "value"}
            assert 0 <= axis["value"] <= 100

        type_tags = response.data["type_tags"]
        assert type_tags == build_type_tags(response.data["type_key"])
        assert response.data["description"]

        assert isinstance(response.data["accuracy"], int)
        assert 0 <= response.data["accuracy"] <= 100

        detail_cards = response.data["detail_cards"]
        assert len(detail_cards) == 4
        for card in detail_cards:
            assert card["title"]
            assert card["description"]

        for key in ("compatible_type", "incompatible_type"):
            travel_type = response.data[key]
            assert travel_type.keys() == {"travel_type_id", "type_key", "type_tags", "name", "image_url", "reason"}
            assert travel_type["type_key"] != response.data["type_key"]
            assert travel_type["type_tags"] == build_type_tags(travel_type["type_key"])

        assert 1 <= len(response.data["destinations"]) <= 3
        destination = response.data["destinations"][0]
        assert destination["place_id"] == place.id
        assert destination["tags"]
        assert destination["style_vector"] == [
            {"label": "액티비티형", "value": 50},
            {"label": "계획형", "value": 50},
            {"label": "혼자형", "value": 50},
            {"label": "자연형", "value": 50},
            {"label": "문화형", "value": 50},
            {"label": "가성비형", "value": 50},
        ]
        assert 0 <= destination["match_rate"] <= 100
