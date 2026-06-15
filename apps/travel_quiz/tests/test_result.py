import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.place.models import PlaceFeature
from apps.travel_quiz.services.travel_quiz_services import build_type_tags, calculate_accuracy, make_description
from apps.travel_quiz.tests.factories import PlaceFactory, TravelTypeFactory, UserFactory, UserTestResultFactory
from apps.user.models import User


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


@pytest.mark.django_db
class TestQuizResultGet:
    def test_퀴즈_결과_조회_성공(self, auth_client: APIClient, user: User) -> None:
        travel_type = TravelTypeFactory(type_key="ttt")
        result = UserTestResultFactory(user=user, travel_type=travel_type)
        place = PlaceFactory()
        PlaceFeature.objects.create(place=place, style_vector=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

        response = auth_client.get("/api/v1/users/quiz/result")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["type_key"] == travel_type.type_key
        assert response.data["name"] == travel_type.name
        assert response.data["description"] == make_description(result.result_vector)
        assert response.data["image_url"] == travel_type.image_url
        assert response.data["type_tags"] == build_type_tags(travel_type.type_key)
        assert response.data["updated_at"] is not None
        assert response.data["accuracy"] == calculate_accuracy(result.result_vector)
        assert 0 <= response.data["accuracy"] <= 100

        result_vector = response.data["result_vector"]
        assert len(result_vector) == 6
        for axis in result_vector:
            assert axis.keys() == {"label", "value"}
            assert 0 <= axis["value"] <= 100

        assert 1 <= len(response.data["destinations"]) <= 3
        destination = response.data["destinations"][0]
        assert destination["place_id"] == place.id
        assert destination["place_name"] == place.place_name
        assert destination.keys() == {"place_id", "place_name", "match_rate"}
        assert 0 <= destination["match_rate"] <= 100

    def test_퀴즈_결과_없음_404(self, auth_client: APIClient) -> None:
        response = auth_client.get("/api/v1/users/quiz/result")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error_detail"] == "퀴즈 결과를 찾을 수 없습니다."

    def test_퀴즈_결과_조회_비로그인_401(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/quiz/result")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error_detail"] == "자격 인증 데이터가 제공되지 않았습니다."
