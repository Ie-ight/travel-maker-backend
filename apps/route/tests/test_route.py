import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.route.models import Route
from apps.route.tests.factories import (
    AdminUserFactory,
    PlaceFactory,
    RouteFactory,
    TagFactory,
    UserFactory,
)
from apps.user.models import User, UserActionLog


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def user() -> User:
    return UserFactory()  # type: ignore[return-value]


@pytest.fixture
def other_user() -> User:
    return UserFactory()  # type: ignore[return-value]


@pytest.fixture
def admin_user() -> User:
    return AdminUserFactory()  # type: ignore[return-value]


@pytest.fixture
def auth_client(client: APIClient, user: User) -> APIClient:
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(client: APIClient, admin_user: User) -> APIClient:
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def tag() -> object:
    return TagFactory()


@pytest.fixture
def place() -> object:
    return PlaceFactory(
        description="아름다운 해변입니다.",
        address_primary="제주특별자치도 제주시",
        address_detail="해변로 123",
    )


@pytest.fixture
def route(user: User) -> Route:
    return RouteFactory(user=user)  # type: ignore[return-value]


def _route_payload(tag_id: int, place_id: int, **kwargs: object) -> dict:
    """경로 생성/수정 기본 페이로드. 공통 필드를 한 곳에서 관리."""
    base = {
        "title": "제주 1박 2일",
        "region_tag_id": tag_id,
        "start_date": "2026-07-01",
        "end_date": "2026-07-02",
        "days": [
            {"day_index": 1, "place_ids": [place_id]},
            {"day_index": 2, "place_ids": [place_id]},
        ],
    }
    base.update(kwargs)
    return base


@pytest.mark.django_db
class TestRouteCreate:
    def test_경로_생성_성공(self, auth_client: APIClient, user: User, tag: object, place: object) -> None:
        response = auth_client.post("/api/v1/routes", _route_payload(tag.id, place.id), format="json")  # type: ignore[attr-defined]
        assert response.status_code == status.HTTP_201_CREATED
        assert "route_id" in response.data
        assert response.data["title"] == "제주 1박 2일"
        assert len(response.data["days"]) == 2
        day1 = response.data["days"][0]
        assert day1["day_index"] == 1
        assert UserActionLog.objects.filter(  # type: ignore[attr-defined]
            user=user, place=place, action_type=UserActionLog.ActionType.ROUTE_ADD
        ).exists()
        assert day1["places"][0]["place_id"] == place.id  # type: ignore[attr-defined]
        assert day1["places"][0]["place_name"] == place.place_name  # type: ignore[attr-defined]
        assert day1["places"][0]["description"] == place.description  # type: ignore[attr-defined]
        assert day1["places"][0]["address_primary"] == place.address_primary  # type: ignore[attr-defined]
        assert day1["places"][0]["address_detail"] == place.address_detail  # type: ignore[attr-defined]

    def test_경로_생성_비인증_실패(self, client: APIClient, tag: object, place: object) -> None:
        response = client.post("/api/v1/routes", _route_payload(tag.id, place.id), format="json")  # type: ignore[attr-defined]
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_제목_20자_초과_실패(self, auth_client: APIClient, tag: object, place: object) -> None:
        payload = _route_payload(tag.id, place.id, title="가" * 21)  # type: ignore[attr-defined]
        response = auth_client.post("/api/v1/routes", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_종료일_이전_시작일_실패(self, auth_client: APIClient, tag: object, place: object) -> None:
        payload = _route_payload(tag.id, place.id, start_date="2026-07-05", end_date="2026-07-01")  # type: ignore[attr-defined]
        response = auth_client.post("/api/v1/routes", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_2박3일_초과_실패(self, auth_client: APIClient, tag: object, place: object) -> None:
        payload = _route_payload(tag.id, place.id, start_date="2026-07-01", end_date="2026-07-04")  # type: ignore[attr-defined]
        response = auth_client.post("/api/v1/routes", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_존재하지_않는_장소_실패(self, auth_client: APIClient, tag: object) -> None:  # type: ignore[attr-defined]
        payload = _route_payload(tag.id, 99999)  # type: ignore[attr-defined]
        response = auth_client.post("/api/v1/routes", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_존재하지_않는_태그_실패(self, auth_client: APIClient, place: object) -> None:  # type: ignore[attr-defined]
        payload = _route_payload(99999, place.id)  # type: ignore[attr-defined]
        response = auth_client.post("/api/v1/routes", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_중복_day_index_실패(self, auth_client: APIClient, tag: object, place: object) -> None:
        payload = _route_payload(tag.id, place.id)  # type: ignore[attr-defined]
        payload["days"] = [
            {"day_index": 1, "place_ids": [place.id]},  # type: ignore[attr-defined]
            {"day_index": 1, "place_ids": [place.id]},  # type: ignore[attr-defined]
        ]
        response = auth_client.post("/api/v1/routes", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestRouteDetail:
    def test_경로_상세_조회_성공(self, client: APIClient, route: Route) -> None:
        response = client.get(f"/api/v1/routes/{route.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["route_id"] == route.id
        assert response.data["user_id"] == route.user_id
        assert response.data["user_nickname"] == route.user.nickname
        assert "days" in response.data

    def test_존재하지_않는_경로_404(self, client: APIClient) -> None:
        response = client.get("/api/v1/routes/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_비인증_상세_조회_성공(self, client: APIClient, route: Route) -> None:
        response = client.get(f"/api/v1/routes/{route.id}")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestRouteUpdate:
    def test_경로_수정_성공(self, auth_client: APIClient, route: Route) -> None:
        response = auth_client.patch(f"/api/v1/routes/{route.id}", {"title": "수정된 경로"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "수정된 경로"
        assert response.data["days"] == []

    def test_경로_수정으로_장소_정보_포함_성공(self, auth_client: APIClient, route: Route, place: object) -> None:
        payload = {"days": [{"day_index": 1, "place_ids": [place.id]}]}  # type: ignore[attr-defined]
        response = auth_client.patch(f"/api/v1/routes/{route.id}", payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["days"]) == 1
        assert response.data["days"][0]["places"][0]["place_id"] == place.id  # type: ignore[attr-defined]

    def test_타인_경로_수정_실패(self, auth_client: APIClient, other_user: User) -> None:
        other_route = RouteFactory(user=other_user)
        response = auth_client.patch(f"/api/v1/routes/{other_route.id}", {"title": "수정"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_비인증_수정_실패(self, client: APIClient, route: Route) -> None:
        response = client.patch(f"/api/v1/routes/{route.id}", {"title": "수정"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_존재하지_않는_경로_수정_실패(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/routes/99999", {"title": "수정"}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestRouteDelete:
    def test_경로_삭제_성공(self, auth_client: APIClient, route: Route) -> None:
        response = auth_client.delete(f"/api/v1/routes/{route.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Route.objects.filter(pk=route.id).exists()

    def test_타인_경로_삭제_실패(self, auth_client: APIClient, other_user: User) -> None:
        other_route = RouteFactory(user=other_user)
        response = auth_client.delete(f"/api/v1/routes/{other_route.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_비인증_삭제_실패(self, client: APIClient, route: Route) -> None:
        response = client.delete(f"/api/v1/routes/{route.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_존재하지_않는_경로_삭제_실패(self, auth_client: APIClient) -> None:
        response = auth_client.delete("/api/v1/routes/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestRouteList:
    def test_경로_목록_조회_성공(self, client: APIClient) -> None:
        RouteFactory.create_batch(3)
        response = client.get("/api/v1/routes")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_비인증_목록_조회_성공(self, client: APIClient) -> None:
        response = client.get("/api/v1/routes")
        assert response.status_code == status.HTTP_200_OK

    def test_지역_태그_필터(self, client: APIClient) -> None:
        tag = TagFactory()
        RouteFactory(region_tag=tag)
        RouteFactory()
        response = client.get(f"/api/v1/routes?region_tag_id={tag.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_인기순_정렬(self, client: APIClient) -> None:
        RouteFactory(like_count=5)
        RouteFactory(like_count=10)
        response = client.get("/api/v1/routes?ordering=popular")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["like_count"] == 10


@pytest.mark.django_db
class TestAdminRouteDelete:
    def test_관리자_경로_삭제_성공(self, admin_client: APIClient, route: Route) -> None:
        response = admin_client.delete(f"/api/v1/admin/routes/{route.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Route.objects.filter(pk=route.id).exists()

    def test_일반유저_관리자_삭제_실패(self, auth_client: APIClient, route: Route) -> None:
        response = auth_client.delete(f"/api/v1/admin/routes/{route.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_비인증_관리자_삭제_실패(self, client: APIClient, route: Route) -> None:
        response = client.delete(f"/api/v1/admin/routes/{route.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_존재하지_않는_경로_삭제_실패(self, admin_client: APIClient) -> None:
        response = admin_client.delete("/api/v1/admin/routes/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
