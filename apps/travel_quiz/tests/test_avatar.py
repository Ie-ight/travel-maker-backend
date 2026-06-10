import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.travel_quiz.tests.factories import TravelTypeFactory, UserFactory
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
class TestQuizAvatarPatch:
    def test_아바타_등록_성공(self, auth_client: APIClient, user: User) -> None:
        travel_type = TravelTypeFactory(image_url="https://example.com/cat.png")

        response = auth_client.patch("/api/v1/users/avatar", {"travel_type_id": travel_type.id}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] is True
        user.refresh_from_db()
        assert user.profile_img_url == travel_type.image_url

    def test_존재하지_않는_travel_type_id_400(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/users/avatar", {"travel_type_id": 999999}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_detail"] == "유효하지 않은 travel_type_id입니다."

    def test_travel_type_id_누락_400(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/users/avatar", {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_비로그인_401(self, client: APIClient) -> None:
        response = client.patch("/api/v1/users/avatar", {"travel_type_id": 1}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error_detail"] == "자격 인증 데이터가 제공되지 않았습니다."
