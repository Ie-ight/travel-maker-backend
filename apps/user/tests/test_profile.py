from io import BytesIO
from unittest.mock import MagicMock, patch

import factory
import pytest
from factory.django import DjangoModelFactory
from PIL import Image as PILImage
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookmark.models import Bookmark
from apps.place.models import Place, Tag
from apps.review.models import Review
from apps.travel_quiz.models import TravelType, UserTestResult
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


class PlaceFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Place

    place_name = factory.Sequence(lambda n: f"place{n}")  # type: ignore[misc]
    content_id = factory.Sequence(lambda n: n + 1)  # type: ignore[misc]
    content_type_id = 12
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


class TagFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Tag

    tag_type = "여행 스타일"
    tag_name = factory.Sequence(lambda n: f"tag{n}")  # type: ignore[misc]


class TravelTypeFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = TravelType

    type_key = factory.Sequence(lambda n: f"k{n:02d}")  # type: ignore[misc]
    name = factory.Sequence(lambda n: f"여행유형{n}")  # type: ignore[misc]
    image_url = "https://example.com/travel-type.png"


class UserTestResultFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = UserTestResult

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    travel_type = factory.SubFactory(TravelTypeFactory)  # type: ignore[misc]
    result_vector = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]


class FollowFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Follow

    follower = factory.SubFactory(UserFactory)  # type: ignore[misc]
    following = factory.SubFactory(UserFactory)  # type: ignore[misc]


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

    def test_프로필_조회_관심태그_포함(self, auth_client: APIClient, user: User) -> None:
        tag = TagFactory()  # type: ignore[misc]
        user.tags.add(tag)

        response = auth_client.get("/api/v1/users")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["tags"] == [{"id": tag.id, "name": tag.tag_name}]

    def test_프로필_조회_여행성향_미응답시_null(self, auth_client: APIClient) -> None:
        response = auth_client.get("/api/v1/users")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["travel_type_name"] is None

    def test_프로필_조회_여행성향_응답시_타입명(self, auth_client: APIClient, user: User) -> None:
        result = UserTestResultFactory(user=user)  # type: ignore[misc]

        response = auth_client.get("/api/v1/users")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["travel_type_name"] == result.travel_type.name

    def test_프로필_조회_팔로워_팔로잉_카운트(self, auth_client: APIClient, user: User) -> None:
        # other1 -> user (other1이 user를 팔로우 = user의 팔로워)
        other1 = UserFactory()  # type: ignore[misc]
        FollowFactory(follower=other1, following=user)  # type: ignore[misc]
        # user -> other2, other3 (user가 팔로우하는 대상 = user의 팔로잉)
        other2 = UserFactory()  # type: ignore[misc]
        other3 = UserFactory()  # type: ignore[misc]
        FollowFactory(follower=user, following=other2)  # type: ignore[misc]
        FollowFactory(follower=user, following=other3)  # type: ignore[misc]

        response = auth_client.get("/api/v1/users")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["follower_count"] == 1
        assert response.data["following_count"] == 2


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

    def test_프로필_이미지_업로드_큐잉(self, auth_client: APIClient, user: User) -> None:
        img = PILImage.new("RGB", (100, 100), color="blue")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.name = "profile.jpg"
        img_bytes.seek(0)

        with patch("apps.user.services.profile_service.upload_profile_image") as mock_task:
            mock_task.delay = MagicMock()
            response = auth_client.patch(
                "/api/v1/users",
                {"profile_image": img_bytes},
                format="multipart",
            )

        assert response.status_code == status.HTTP_200_OK
        mock_task.delay.assert_called_once()
        called_user_id = mock_task.delay.call_args[0][0]
        assert called_user_id == user.id

    def test_프로필_수정_응답에_profile_img_url_쓰기_불가(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/users", {"profile_img_url": "https://evil.example.com/x.png"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["profile_img_url"] != "https://evil.example.com/x.png"


@pytest.mark.django_db
class TestNicknameCheck:
    def test_사용가능한_닉네임_200(self, client: APIClient) -> None:
        response = client.post("/api/v1/users/nickname/check", {"nickname": "신규닉네임"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "사용가능한 닉네임 입니다."

    def test_닉네임_누락_400(self, client: APIClient) -> None:
        response = client.post("/api/v1/users/nickname/check", {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_중복_닉네임_409(self, client: APIClient, user: User) -> None:
        response = client.post("/api/v1/users/nickname/check", {"nickname": user.nickname})

        assert response.status_code == status.HTTP_409_CONFLICT


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
