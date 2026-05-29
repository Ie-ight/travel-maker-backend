import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.bookmark.models import Bookmark
from apps.place.models import Place

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
    latitude = "37.1234567"
    longitude = "127.1234567"


class BookmarkFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Bookmark

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    place = factory.SubFactory(PlaceFactory)  # type: ignore[misc]
