import factory
import pytest
from factory.django import DjangoModelFactory
from rest_framework import status
from rest_framework.test import APIClient

from apps.place.models import Place
from apps.review.models import Review
from apps.user.models import Follow, User


# Factories
class UserFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.com")  # type: ignore[misc]
    nickname = factory.Sequence(lambda n: f"t_{n:04d}")  # type: ignore[misc]
    gender = "M"
    birthday = "2000-01-01"
    is_active = True


class FollowFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Follow

    follower = factory.SubFactory(UserFactory)  # type: ignore[misc]
    following = factory.SubFactory(UserFactory)  # type: ignore[misc]


class PlaceFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Place

    place_name = factory.Sequence(lambda n: f"place{n}")  # type: ignore[misc]
    content_id = factory.Sequence(lambda n: n + 1)  # type: ignore[misc]
    content_type_id = 12
    latitude = "37.1234567"
    longitude = "127.1234567"


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
class TestFollowCreate:
    def test_팔로우_성공(self, auth_client: APIClient, user: User) -> None:
        target = UserFactory()  # type: ignore[misc]

        response = auth_client.post(f"/api/v1/users/{target.id}/follow")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["detail"] == "팔로우했습니다."
        assert Follow.objects.filter(follower=user, following=target).exists()

    def test_자기_자신_팔로우_400(self, auth_client: APIClient, user: User) -> None:
        response = auth_client.post(f"/api/v1/users/{user.id}/follow")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_존재하지_않는_유저_팔로우_404(self, auth_client: APIClient) -> None:
        response = auth_client.post("/api/v1/users/999999/follow")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_중복_팔로우_409(self, auth_client: APIClient, user: User) -> None:
        target = UserFactory()  # type: ignore[misc]
        FollowFactory(follower=user, following=target)  # type: ignore[misc]

        response = auth_client.post(f"/api/v1/users/{target.id}/follow")

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_비로그인_팔로우_401(self, client: APIClient) -> None:
        target = UserFactory()  # type: ignore[misc]

        response = client.post(f"/api/v1/users/{target.id}/follow")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestFollowDelete:
    def test_언팔로우_성공(self, auth_client: APIClient, user: User) -> None:
        target = UserFactory()  # type: ignore[misc]
        FollowFactory(follower=user, following=target)  # type: ignore[misc]

        response = auth_client.delete(f"/api/v1/users/{target.id}/follow")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Follow.objects.filter(follower=user, following=target).exists()

    def test_팔로우_관계_없음_404(self, auth_client: APIClient) -> None:
        target = UserFactory()  # type: ignore[misc]

        response = auth_client.delete(f"/api/v1/users/{target.id}/follow")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_비로그인_언팔로우_401(self, client: APIClient) -> None:
        target = UserFactory()  # type: ignore[misc]

        response = client.delete(f"/api/v1/users/{target.id}/follow")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestFollowerFollowingList:
    def test_팔로워_목록_조회(self, client: APIClient, user: User) -> None:
        follower = UserFactory()  # type: ignore[misc]
        FollowFactory(follower=follower, following=user)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{user.id}/followers")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {"user_id": follower.id, "nickname": follower.nickname, "profile_img_url": follower.profile_img_url}
        ]

    def test_팔로잉_목록_조회(self, client: APIClient, user: User) -> None:
        following = UserFactory()  # type: ignore[misc]
        FollowFactory(follower=user, following=following)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{user.id}/following")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {"user_id": following.id, "nickname": following.nickname, "profile_img_url": following.profile_img_url}
        ]

    def test_존재하지_않는_유저_팔로워_목록_404(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/999999/followers")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_존재하지_않는_유저_팔로잉_목록_404(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/999999/following")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_탈퇴한_유저_팔로워_목록_404(self, client: APIClient) -> None:
        target = UserFactory(is_active=False)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{target.id}/followers")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_탈퇴한_유저_팔로잉_목록_404(self, client: APIClient) -> None:
        target = UserFactory(is_active=False)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{target.id}/following")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPublicProfile:
    def test_공개_프로필_조회_성공(self, client: APIClient, user: User) -> None:
        response = client.get(f"/api/v1/users/{user.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["nickname"] == user.nickname
        assert "email" not in response.data
        assert "bookmark_count" not in response.data
        assert "review_count" not in response.data

    def test_존재하지_않는_유저_공개_프로필_404(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/999999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_탈퇴한_유저_공개_프로필_404(self, client: APIClient) -> None:
        target = UserFactory(is_active=False)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{target.id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPublicUserReviewList:
    def test_공개_리뷰_목록_조회_성공(self, client: APIClient, user: User) -> None:
        ReviewFactory.create_batch(2, user=user)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{user.id}/reviews")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_존재하지_않는_유저_공개_리뷰_목록_404(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/999999/reviews")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_탈퇴한_유저_공개_리뷰_목록_404(self, client: APIClient) -> None:
        target = UserFactory(is_active=False)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{target.id}/reviews")

        assert response.status_code == status.HTTP_404_NOT_FOUND
