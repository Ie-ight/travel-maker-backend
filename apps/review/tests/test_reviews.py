from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage
from rest_framework import status
from rest_framework.test import APIClient

from apps.place.models import Place
from apps.review.models import Review
from apps.review.tests.factories import PlaceFactory, ReviewFactory, UserFactory
from apps.user.models import User


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


@pytest.fixture
def other_user() -> User:
    return UserFactory()  # type: ignore[return-value]


@pytest.mark.django_db
class TestReviewList:
    def test_리뷰_목록_조회_성공(self, client: APIClient, place: Place) -> None:
        ReviewFactory.create_batch(3, place=place)  # type: ignore[misc]
        response = client.get(f"/api/v1/places/{place.id}/reviews")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert "avg_rating" in response.data
        assert "results" in response.data

    def test_리뷰_목록_기본_4개_반환(self, client: APIClient, place: Place) -> None:
        ReviewFactory.create_batch(6, place=place)  # type: ignore[misc]
        response = client.get(f"/api/v1/places/{place.id}/reviews")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 4

    def test_리뷰_목록_비인증_조회_성공(self, client: APIClient, place: Place) -> None:
        response = client.get(f"/api/v1/places/{place.id}/reviews")
        assert response.status_code == status.HTTP_200_OK

    def test_존재하지_않는_장소_404(self, client: APIClient) -> None:
        response = client.get("/api/v1/places/99999/reviews")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestReviewCreate:
    def test_이미지_포함_리뷰_등록_성공(self, auth_client: APIClient, place: Place) -> None:
        img = PILImage.new("RGB", (100, 100), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.name = "test.jpg"
        img_bytes.seek(0)

        with patch("apps.review.services.review_services.upload_review_image") as mock_task:
            mock_task.delay = MagicMock()
            response = auth_client.post(
                f"/api/v1/places/{place.id}/reviews",
                {"rating": 5, "content": "좋아요!", "image": img_bytes},
                format="multipart",
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_리뷰_비인증_등록_실패(self, client: APIClient, place: Place) -> None:
        response = client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 5, "content": "좋아요!"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_리뷰_중복_등록_실패(self, auth_client: APIClient, user: User, place: Place) -> None:
        ReviewFactory(user=user, place=place)  # type: ignore[misc]
        response = auth_client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 5, "content": "또 쓰기"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_별점_범위_초과_실패(self, auth_client: APIClient, place: Place) -> None:
        response = auth_client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 6, "content": "좋아요!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_존재하지_않는_장소_등록_실패(self, auth_client: APIClient) -> None:
        response = auth_client.post(
            "/api/v1/places/99999/reviews",
            {"rating": 5, "content": "좋아요!"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestReviewUpdate:
    def test_리뷰_수정_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        review = ReviewFactory(user=user, place=place)  # type: ignore[misc]
        response = auth_client.patch(
            f"/api/v1/reviews/{review.id}",
            {"rating": 3, "content": "다시 생각해보니"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["rating"] == 3

    def test_리뷰_수정_비인증_실패(self, client: APIClient) -> None:
        response = client.patch("/api/v1/reviews/1", {"rating": 3})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_타인_리뷰_수정_실패(self, auth_client: APIClient, other_user: User, place: Place) -> None:
        review = ReviewFactory(user=other_user, place=place)  # type: ignore[misc]
        response = auth_client.patch(
            f"/api/v1/reviews/{review.id}",
            {"rating": 1},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_존재하지_않는_리뷰_수정_실패(self, auth_client: APIClient) -> None:
        response = auth_client.patch("/api/v1/reviews/99999", {"rating": 3})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_빈_요청_수정_실패(self, auth_client: APIClient, user: User, place: Place) -> None:
        review = ReviewFactory(user=user, place=place)  # type: ignore[misc]
        response = auth_client.patch(f"/api/v1/reviews/{review.id}", {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestReviewDelete:
    def test_리뷰_삭제_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        review = ReviewFactory(user=user, place=place)  # type: ignore[misc]
        response = auth_client.delete(f"/api/v1/reviews/{review.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Review.objects.count() == 0  # type: ignore[attr-defined]

    def test_리뷰_삭제_비인증_실패(self, client: APIClient) -> None:
        response = client.delete("/api/v1/reviews/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_타인_리뷰_삭제_실패(self, auth_client: APIClient, other_user: User, place: Place) -> None:
        review = ReviewFactory(user=other_user, place=place)  # type: ignore[misc]
        response = auth_client.delete(f"/api/v1/reviews/{review.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_존재하지_않는_리뷰_삭제_실패(self, auth_client: APIClient) -> None:
        response = auth_client.delete("/api/v1/reviews/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
