import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.place.models import Place
from apps.review.models import Review
from apps.review.tests.factories import PlaceFactory, ReviewFactory, UserFactory
from apps.route.models import Route, RouteDay, RouteDayPlace
from apps.route.tests.factories import RouteFactory
from apps.user.models import User, UserActionLog


def _create_route_with_place(user: User, place: Place) -> Route:
    route = RouteFactory(user=user)  # type: ignore[misc]
    day = RouteDay.objects.create(route=route, day_index=1)
    RouteDayPlace.objects.create(route_day=day, place=place, order=1)
    return route  # type: ignore[no-any-return]


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

    def test_리뷰_목록_조회_시_본인_리뷰_is_owner_필드_확인(
        self, auth_client: APIClient, user: User, place: Place
    ) -> None:
        other_user = UserFactory()  # type: ignore[misc]
        my_review = ReviewFactory(user=user, place=place)  # type: ignore[misc]
        other_review = ReviewFactory(user=other_user, place=place)  # type: ignore[misc]

        response = auth_client.get(f"/api/v1/places/{place.id}/reviews")
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        assert len(results) == 2

        my_res = next(r for r in results if r["review_id"] == my_review.id)
        other_res = next(r for r in results if r["review_id"] == other_review.id)

        assert my_res["is_owner"] is True
        assert other_res["is_owner"] is False

    def test_리뷰_목록_조회_시_비로그인_is_owner_모두_false(self, client: APIClient, place: Place) -> None:
        ReviewFactory.create_batch(2, place=place)  # type: ignore[misc]
        response = client.get(f"/api/v1/places/{place.id}/reviews")
        assert response.status_code == status.HTTP_200_OK
        for result in response.data["results"]:
            assert result["is_owner"] is False


@pytest.mark.django_db
class TestReviewCreate:
    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_이미지_포함_리뷰_등록_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        image_url = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/reviews/test.jpg"
        response = auth_client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 5, "content": "좋아요!", "image_url": image_url},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_owner"] is True
        assert response.data["image_url"] == image_url
        assert UserActionLog.objects.filter(  # type: ignore[attr-defined]
            user=user, place=place, action_type=UserActionLog.ActionType.REVIEW
        ).exists()

    def test_평점_3점_리뷰_등록시_행동로그_생성안됨(self, auth_client: APIClient, user: User, place: Place) -> None:
        response = auth_client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 3, "content": "보통이에요"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert not UserActionLog.objects.filter(  # type: ignore[attr-defined]
            user=user, place=place, action_type=UserActionLog.ActionType.REVIEW
        ).exists()

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
        assert response.data["is_owner"] is True

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


@pytest.mark.django_db
class TestReviewRoute:
    def test_경로_연결하여_리뷰_등록_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        route = _create_route_with_place(user, place)
        response = auth_client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 5, "content": "이 경로로 다녀왔어요!", "route_id": route.id},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["route"]["route_id"] == route.id
        assert response.data["route"]["title"] == route.title

    def test_타인_소유_경로_연결_등록_실패_404(self, auth_client: APIClient, other_user: User, place: Place) -> None:
        route = _create_route_with_place(other_user, place)
        response = auth_client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 5, "content": "좋아요!", "route_id": route.id},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_장소가_포함되지_않은_경로_연결_등록_실패_400(
        self, auth_client: APIClient, user: User, place: Place
    ) -> None:
        other_place = PlaceFactory()  # type: ignore[misc]
        route = _create_route_with_place(user, other_place)
        response = auth_client.post(
            f"/api/v1/places/{place.id}/reviews",
            {"rating": 5, "content": "좋아요!", "route_id": route.id},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_리뷰_수정으로_경로_연결_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        review = ReviewFactory(user=user, place=place)  # type: ignore[misc]
        route = _create_route_with_place(user, place)
        response = auth_client.patch(
            f"/api/v1/reviews/{review.id}",
            {"route_id": route.id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["route"]["route_id"] == route.id

    def test_리뷰_수정으로_경로_연결_해제_성공(self, auth_client: APIClient, user: User, place: Place) -> None:
        route = _create_route_with_place(user, place)
        review = ReviewFactory(user=user, place=place, route=route)  # type: ignore[misc]
        response = auth_client.patch(
            f"/api/v1/reviews/{review.id}",
            {"route_id": None},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["route"] is None
