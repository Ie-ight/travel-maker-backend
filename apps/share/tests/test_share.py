import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.place.models import Place
from apps.route.models import Route
from apps.share.tests.factories import (
    PlaceFactory,
    RouteFactory,
    TravelTypeFactory,
    UserFactory,
    UserTestResultFactory,
)
from apps.travel_quiz.models import UserTestResult
from apps.user.models import User

URL = reverse("share")
FRONTEND = "http://testserver-frontend"


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
def place() -> Place:
    return PlaceFactory()  # type: ignore[return-value]


@pytest.fixture
def route(user: User) -> Route:
    return RouteFactory(user=user)  # type: ignore[return-value]


@pytest.fixture
def quiz_result(user: User) -> UserTestResult:
    travel_type = TravelTypeFactory(type_key="ENF")  # type: ignore[misc]
    return UserTestResultFactory(user=user, travel_type=travel_type)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# place 공유
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestSharePlace:
    def test_장소_공유_URL_생성_성공(self, client: APIClient, place: Place) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, {"content_type": "place", "content_id": place.id})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["share_url"] == f"{FRONTEND}/place/{place.id}"

    def test_장소_공유_비로그인도_가능(self, client: APIClient, place: Place) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, {"content_type": "place", "content_id": place.id})

        assert response.status_code == status.HTTP_200_OK

    def test_로그인_사용자도_장소_공유_가능(self, auth_client: APIClient, place: Place) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = auth_client.post(URL, {"content_type": "place", "content_id": place.id})

        assert response.status_code == status.HTTP_200_OK

    def test_비활성_장소_공유_404(self, client: APIClient) -> None:
        inactive_place = PlaceFactory(is_active=False)  # type: ignore[misc]
        response = client.post(URL, {"content_type": "place", "content_id": inactive_place.id})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error_detail" in response.data

    def test_존재하지_않는_장소_공유_404(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "place", "content_id": 99999})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error_detail" in response.data


# ---------------------------------------------------------------------------
# route 공유
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestShareRoute:
    def test_경로_공유_URL_생성_성공(self, client: APIClient, route: Route) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, {"content_type": "route", "content_id": route.id})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["share_url"] == f"{FRONTEND}/route/{route.id}"

    def test_경로_공유_비로그인도_가능(self, client: APIClient, route: Route) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, {"content_type": "route", "content_id": route.id})

        assert response.status_code == status.HTTP_200_OK

    def test_존재하지_않는_경로_공유_404(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "route", "content_id": 99999})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error_detail" in response.data


# ---------------------------------------------------------------------------
# travel_quiz 공유
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestShareTravelQuiz:
    def test_성향테스트_결과_공유_URL_생성_성공(
        self, client: APIClient, user: User, quiz_result: UserTestResult
    ) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, {"content_type": "travel_quiz", "content_id": user.id})

        assert response.status_code == status.HTTP_200_OK
        share_url: str = response.data["share_url"]
        assert f"{FRONTEND}/quiz/result" in share_url
        assert "type_key=ENF" in share_url
        assert "vector=" in share_url

    def test_성향테스트_결과_공유_벡터_값_포함(
        self, client: APIClient, user: User, quiz_result: UserTestResult
    ) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, {"content_type": "travel_quiz", "content_id": user.id})

        share_url: str = response.data["share_url"]
        # 6차원 벡터가 쿼리스트링에 포함되어 있는지 확인 (쉼표로 구분된 6개 값)
        vector_part = next(p for p in share_url.split("&") if p.startswith("vector="))
        values = vector_part.split("=")[1].split(",")
        assert len(values) == 6

    def test_성향테스트_공유_비로그인도_가능(self, client: APIClient, user: User, quiz_result: UserTestResult) -> None:
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, {"content_type": "travel_quiz", "content_id": user.id})

        assert response.status_code == status.HTTP_200_OK

    def test_테스트_결과_없는_유저_공유_404(self, client: APIClient) -> None:
        user_without_result = UserFactory()  # type: ignore[misc]
        response = client.post(URL, {"content_type": "travel_quiz", "content_id": user_without_result.id})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error_detail" in response.data

    def test_존재하지_않는_유저_공유_404(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "travel_quiz", "content_id": 99999})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_비로그인_유저_type_key_vector_직접_공유_성공(self, client: APIClient) -> None:
        payload = {
            "content_type": "travel_quiz",
            "type_key": "ENF",
            "vector": [0.8, 0.6, 0.4, 0.3, 0.7, 0.5],
        }
        with override_settings(FRONTEND_URL=FRONTEND):
            response = client.post(URL, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        share_url: str = response.data["share_url"]
        assert "type_key=ENF" in share_url
        assert "vector=" in share_url
        values = share_url.split("vector=")[1].split(",")
        assert len(values) == 6

    def test_travel_quiz_content_id도_vector도_없으면_400(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "travel_quiz"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_travel_quiz_type_key만_있고_vector_없으면_400(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "travel_quiz", "type_key": "ENF"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_travel_quiz_vector_차원_수_오류_400(self, client: APIClient) -> None:
        payload = {
            "content_type": "travel_quiz",
            "type_key": "ENF",
            "vector": [0.5, 0.5],  # 6차원이어야 함
        }
        response = client.post(URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# 입력 유효성 검사
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestShareValidation:
    def test_잘못된_content_type_400(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "invalid_type", "content_id": 1})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_content_type_누락_400(self, client: APIClient) -> None:
        response = client.post(URL, {"content_id": 1})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_content_id_누락_400(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "place"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_content_id_음수_400(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "place", "content_id": -1})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_content_id_0_400(self, client: APIClient) -> None:
        response = client.post(URL, {"content_type": "place", "content_id": 0})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_빈_요청_400(self, client: APIClient) -> None:
        response = client.post(URL, {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
