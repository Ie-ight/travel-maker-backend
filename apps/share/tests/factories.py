import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.place.models import Place
from apps.route.models import Route, Tag
from apps.travel_quiz.models import TravelType, UserTestResult

User = get_user_model()


class UserFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"share_user{n}@test.com")  # type: ignore[misc]
    nickname = factory.Sequence(lambda n: f"s_{n:04d}")  # type: ignore[misc]
    gender = "M"
    birthday = "2000-01-01"
    is_active = True


class PlaceFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Place

    place_name = factory.Sequence(lambda n: f"공유장소{n}")  # type: ignore[misc]
    content_id = factory.Sequence(lambda n: n + 9000)  # type: ignore[misc]
    content_type_id = 12
    latitude = "37.1234567"
    longitude = "127.1234567"
    is_active = True


class TagFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Tag

    tag_type = "지역"
    tag_name = factory.Sequence(lambda n: f"지역태그{n}")  # type: ignore[misc]


class RouteFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Route

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    title = factory.Sequence(lambda n: f"공유경로{n}")  # type: ignore[misc]
    start_date = "2026-07-01"
    end_date = "2026-07-02"
    like_count = 0


class TravelTypeFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = TravelType

    type_key = factory.Sequence(lambda n: f"s{n:02d}")  # type: ignore[misc]
    name = factory.Sequence(lambda n: f"공유유형{n}")  # type: ignore[misc]
    image_url = "https://example.com/type.png"


class UserTestResultFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = UserTestResult

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    travel_type = factory.SubFactory(TravelTypeFactory)  # type: ignore[misc]
    result_vector = [0.8, 0.6, 0.4, 0.3, 0.7, 0.5]
