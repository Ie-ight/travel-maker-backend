import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.route.models import Route, RouteLike
from apps.route.tests.factories import (
    AdminUserFactory,
    PlaceFactory,
    RouteFactory,
    RouteLikeFactory,
    TagFactory,
    UserFactory,
)
from apps.user.models import User


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
    return PlaceFactory()


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
    def test_경로_생성_성공(self, auth_client: APIClient, tag: object, place: object) -> None:
        response = auth_client.post("/api/v1/routes", _route_payload(tag.id, place.id), format="json")  # type: ignore[attr-defined]
        assert response.status_code == status.HTTP_201_CREATED
        assert "route_id" in response.data
        assert response.data["title"] == "제주 1박 2일"
        assert len(response.data["days"]) == 2
        day1 = response.data["days"][0]
        assert day1["day_index"] == 1
        assert day1["places"][0]["place_id"] == place.id  # type: ignore[attr-defined]
        assert day1["places"][0]["place_name"] == place.place_name  # type: ignore[attr-defined]

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

    def test_4박5일_초과_실패(self, auth_client: APIClient, tag: object, place: object) -> None:
        payload = _route_payload(tag.id, place.id, start_date="2026-07-01", end_date="2026-07-06")  # type: ignore[attr-defined]
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
class TestUserRouteList:
    def test_내_경로_목록_조회_성공(self, auth_client: APIClient, user: User) -> None:
        RouteFactory.create_batch(2, user=user)
        response = auth_client.get(f"/api/v1/users/{user.nickname}/routes")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_비인증_마이페이지_조회_실패(self, client: APIClient, user: User) -> None:
        response = client.get(f"/api/v1/users/{user.nickname}/routes")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_존재하지_않는_유저_404(self, auth_client: APIClient) -> None:
        response = auth_client.get("/api/v1/users/없는유저/routes")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestRouteLike:
    def test_좋아요_등록_성공(self, auth_client: APIClient, route: Route) -> None:
        response = auth_client.post(f"/api/v1/routes/{route.id}/like")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["like_count"] == 1

    def test_좋아요_중복_실패(self, auth_client: APIClient, user: User, route: Route) -> None:
        RouteLikeFactory(route=route, user=user)
        response = auth_client.post(f"/api/v1/routes/{route.id}/like")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_존재하지_않는_경로_좋아요_실패(self, auth_client: APIClient) -> None:
        response = auth_client.post("/api/v1/routes/99999/like")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_비인증_좋아요_실패(self, client: APIClient, route: Route) -> None:
        response = client.post(f"/api/v1/routes/{route.id}/like")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_좋아요_취소_성공(self, auth_client: APIClient, user: User) -> None:
        # like_count=1 로 생성해야 취소 시 0으로 감소 (0에서 감소하면 DB 제약 위반)
        route = RouteFactory(user=user, like_count=1)
        RouteLikeFactory(route=route, user=user)
        response = auth_client.delete(f"/api/v1/routes/{route.id}/like")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not RouteLike.objects.filter(route=route, user=user).exists()

    def test_좋아요_내역_없음_취소_실패(self, auth_client: APIClient, route: Route) -> None:
        response = auth_client.delete(f"/api/v1/routes/{route.id}/like")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestUserLikedRoutes:
    def test_좋아요한_경로_목록_성공(self, auth_client: APIClient, user: User) -> None:
        routes = RouteFactory.create_batch(2)
        RouteLikeFactory(route=routes[0], user=user)
        RouteLikeFactory(route=routes[1], user=user)
        response = auth_client.get("/api/v1/users/routes/likes")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_비인증_좋아요_목록_실패(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/routes/likes")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


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
