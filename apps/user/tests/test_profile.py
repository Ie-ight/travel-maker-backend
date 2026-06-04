import factory
import pytest
from factory.django import DjangoModelFactory
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookmark.models import Bookmark
from apps.place.models import Place
from apps.review.models import Review
from apps.user.models import User


# Factories
class UserFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.com")  # type: ignore[misc]
    nickname = factory.Sequence(lambda n: f"t_{n:04d}")  # type: ignore[misc]
    gender = "M"
    birthday = "2000-01-01"
    is_active = True


class PlaceFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Place

    place_name = factory.Sequence(lambda n: f"place{n}")  # type: ignore[misc]
    latitude = "37.1234567"
    longitude = "127.1234567"


class BookmarkFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Bookmark

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    place = factory.SubFactory(PlaceFactory)  # type: ignore[misc]


class ReviewFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Review

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    place = factory.SubFactory(PlaceFactory)  # type: ignore[misc]
    rating = 5
    content = "테스트 리뷰입니다."


# Fixtures
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


# Tests
@pytest.mark.django_db
class TestProfileGet:
    def test_프로필_조회_성공(self, auth_client: APIClient, user: User) -> None:
        response = auth_client.get("/api/v1/users")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email
        assert response.data["nickname"] == user.nickname

    def test_프로필_조회_비로그인_실패(self, client: APIClient) -> None:
        response = client.get("/api/v1/users")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestProfilePatch:
    def test_프로필_수정_성공(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/users", {"nickname": "수정닉네임"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["nickname"] == "수정닉네임"

    def test_프로필_수정_닉네임_중복_실패(self, auth_client: APIClient) -> None:
        UserFactory(nickname="중복닉네임")  # type: ignore[misc]
        response = auth_client.patch("/api/v1/users", {"nickname": "중복닉네임"})
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_프로필_수정_닉네임_형식_실패(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/users", {"nickname": "invalid!"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_프로필_수정_비로그인_실패(self, client: APIClient) -> None:
        response = client.patch("/api/v1/users", {"nickname": "테스트"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserBookmarkList:
    def test_북마크_목록_조회_성공(self, auth_client: APIClient, user: User) -> None:
        BookmarkFactory.create_batch(3, user=user)  # type: ignore[misc]
        response = auth_client.get("/api/v1/users/bookmarks")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_북마크_목록_비로그인_실패(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/bookmarks")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserReviewList:
    def test_리뷰_목록_조회_성공(self, auth_client: APIClient, user: User) -> None:
        ReviewFactory.create_batch(3, user=user)  # type: ignore[misc]
        response = auth_client.get("/api/v1/users/reviews")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_리뷰_목록_비로그인_실패(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/reviews")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
