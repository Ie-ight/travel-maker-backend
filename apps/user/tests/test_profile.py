from unittest.mock import MagicMock, patch

import factory
import pytest
from django.test import override_settings
from factory.django import DjangoModelFactory
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookmark.models import Bookmark
from apps.place.models import Place, Tag
from apps.review.models import Review
from apps.route.tests.factories import RouteFactory, RouteLikeFactory
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
class TestPublicProfileGet:
    def test_비로그인_조회시_is_following_false(self, client: APIClient, user: User) -> None:
        response = client.get(f"/api/v1/users/{user.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_following"] is False

    def test_로그인_팔로우_안한_상태_is_following_false(self, auth_client: APIClient, user: User) -> None:
        target = UserFactory()  # type: ignore[misc]

        response = auth_client.get(f"/api/v1/users/{target.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_following"] is False

    def test_로그인_팔로우한_상태_is_following_true(self, auth_client: APIClient, user: User) -> None:
        target = UserFactory()  # type: ignore[misc]
        FollowFactory(follower=user, following=target)  # type: ignore[misc]

        response = auth_client.get(f"/api/v1/users/{target.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_following"] is True

    def test_공개_프로필_여행성향_타입명_포함(self, client: APIClient, user: User) -> None:
        result = UserTestResultFactory(user=user)  # type: ignore[misc]

        response = client.get(f"/api/v1/users/{user.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["travel_type_name"] == result.travel_type.name


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

    def test_프로필_수정_응답에_profile_img_url_쓰기_불가(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/users", {"profile_img_url": "https://evil.example.com/x.png"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["profile_img_url"] != "https://evil.example.com/x.png"

    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_프로필_이미지_URL_수정_성공(self, auth_client: APIClient, user: User) -> None:
        profile_image_url = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/profiles/new_avatar.jpg"

        response = auth_client.patch("/api/v1/users", {"profile_image_url": profile_image_url})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["profile_img_url"] == profile_image_url
        user.refresh_from_db()
        assert user.profile_img_url == profile_image_url

    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_프로필_이미지_URL_수정시_기존_이미지_삭제됨(self, auth_client: APIClient, user: User) -> None:
        old_url = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/profiles/old_avatar.jpg"
        new_url = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/profiles/new_avatar.jpg"
        user.profile_img_url = old_url
        user.save(update_fields=["profile_img_url"])

        mock_handler = MagicMock()
        mock_handler.key_from_img_url.return_value = "profiles/old_avatar.jpg"

        with patch("apps.core.presigned_url.services.get_s3_handler", return_value=mock_handler):
            response = auth_client.patch("/api/v1/users", {"profile_image_url": new_url})

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.profile_img_url == new_url
        mock_handler.key_from_img_url.assert_called_once_with(old_url)
        mock_handler.delete_object.assert_called_once_with("profiles/old_avatar.jpg")

    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_프로필_이미지_URL_S3_버킷_아니면_400(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/users", {"profile_image_url": "https://evil.example.com/x.png"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_detail"]["profile_image_url"] == ["유효하지 않은 이미지 URL입니다."]


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
class TestProfileImagePresignedUrl:
    def test_presigned_url_발급_성공(self, auth_client: APIClient, user: User) -> None:
        mock_handler = MagicMock()
        mock_handler.presigned_url_for_upload.return_value = "https://example.com/presigned-put-url"
        mock_handler.img_url.return_value = "https://example.com/profile-images/new.jpg"

        with patch("apps.core.presigned_url.services.get_s3_handler", return_value=mock_handler):
            response = auth_client.patch(
                "/api/v1/users/profile-image/presigned-url",
                {"file_name": "avatar.jpg"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["presigned_url"] == "https://example.com/presigned-put-url"
        assert response.data["img_url"] == "https://example.com/profile-images/new.jpg"
        assert response.data["key"].startswith("profiles/")
        assert response.data["content_type"] == "image/jpeg"

        user.refresh_from_db()
        assert user.profile_img_url != "https://example.com/profile-images/new.jpg"
        mock_handler.delete_object.assert_not_called()

    def test_지원하지_않는_파일_형식_400(self, auth_client: APIClient) -> None:
        response = auth_client.patch(
            "/api/v1/users/profile-image/presigned-url",
            {"file_name": "avatar.exe"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_detail"] == "지원하지 않는 파일 형식입니다."

    def test_비로그인_401(self, client: APIClient) -> None:
        response = client.patch(
            "/api/v1/users/profile-image/presigned-url",
            {"file_name": "avatar.jpg"},
        )

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

    def test_리뷰_목록_조회시_이미지_URL_포함(self, auth_client: APIClient, user: User) -> None:
        image_url = "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/reviews/test.jpg"
        ReviewFactory(user=user, image_url=image_url)  # type: ignore[misc]

        response = auth_client.get("/api/v1/users/reviews")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["image_url"] == image_url

    def test_리뷰_목록_비로그인_실패(self, client: APIClient) -> None:
        response = client.get("/api/v1/users/reviews")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


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
