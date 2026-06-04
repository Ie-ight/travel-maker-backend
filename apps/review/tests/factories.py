import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.place.models import Place
from apps.review.models import Review

User = get_user_model()


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
    rating_avg = 0


class ReviewFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Review

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    place = factory.SubFactory(PlaceFactory)  # type: ignore[misc]
    rating = 5
    content = "좋아요!"
