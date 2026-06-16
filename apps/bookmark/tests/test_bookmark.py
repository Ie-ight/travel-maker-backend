import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookmark.models import Bookmark
from apps.bookmark.tests.factories import BookmarkFactory, PlaceFactory, UserFactory
from apps.place.models import Place
from apps.user.models import User, UserActionLog


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def user() -> User:
    return UserFactory()  # type: ignore[return-value]


@pytest.fixture
def place() -> Place:
    return PlaceFactory()  # type: ignore[return-value]


@pytest.fixture
def auth_client(client: APIClient, user: User) -> APIClient:
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestBookmarkList:
    def test_북마크_목록_조회_성공(self, auth_client: APIClient, user: User) -> None:
        BookmarkFactory.create_batch(3, user=user)  # type: ignore[misc]
        response = auth_client.get("/api/v1/bookmarks/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    def test_북마크_목록_비로그인_실패(self, client: APIClient) -> None:
        response = client.get("/api/v1/bookmarks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBookmarkCreate:
    def test_북마크_추가_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        response = auth_client.post(f"/api/v1/places/{place.id}/bookmarks/")
        assert response.status_code == status.HTTP_201_CREATED
        assert Bookmark.objects.count() == 1  # type: ignore[attr-defined]
        assert UserActionLog.objects.filter(  # type: ignore[attr-defined]
            user=user, place=place, action_type=UserActionLog.ActionType.BOOKMARK
        ).exists()

    def test_북마크_중복_추가_실패(self, auth_client: APIClient, user: User, place: Place) -> None:
        BookmarkFactory(user=user, place=place)  # type: ignore[misc]
        response = auth_client.post(f"/api/v1/places/{place.id}/bookmarks/")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_북마크_비로그인_실패(self, client: APIClient, place: Place) -> None:
        response = client.post(f"/api/v1/places/{place.id}/bookmarks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBookmarkDelete:
    def test_북마크_삭제_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        BookmarkFactory(user=user, place=place)  # type: ignore[misc]
        response = auth_client.delete(f"/api/v1/places/{place.id}/bookmarks/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Bookmark.objects.count() == 0  # type: ignore[attr-defined]
        assert UserActionLog.objects.filter(  # type: ignore[attr-defined]
            user=user, place=place, action_type=UserActionLog.ActionType.UNBOOKMARK
        ).exists()

    def test_북마크_없는거_삭제_실패(self, auth_client: APIClient, place: Place) -> None:
        response = auth_client.delete(f"/api/v1/places/{place.id}/bookmarks/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_북마크_비로그인_삭제_실패(self, client: APIClient, place: Place) -> None:
        response = client.delete(f"/api/v1/places/{place.id}/bookmarks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
