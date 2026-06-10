import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.place.models import Place, Tag
from apps.route.models import Route, RouteLike

User = get_user_model()


class UserFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.com")
    nickname = factory.Sequence(lambda n: f"user_{n:04d}")
    gender = "M"
    birthday = "2000-01-01"
    is_active = True


class AdminUserFactory(UserFactory):  # type: ignore[misc]
    role = "ADMIN"
    is_staff = True


class TagFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Tag

    tag_type = "지역"
    tag_name = factory.Sequence(lambda n: f"태그{n}")


class PlaceFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Place

    place_name = factory.Sequence(lambda n: f"장소{n}")
    content_id = factory.Sequence(lambda n: n + 5000)
    content_type_id = 12
    latitude = "37.123456"
    longitude = "127.123456"
    is_active = True


class RouteFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Route

    user = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"경로{n}")
    description = "테스트 경로"
    region_tag = factory.SubFactory(TagFactory)
    start_date = "2026-07-01"
    end_date = "2026-07-02"
    like_count = 0


class RouteLikeFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = RouteLike

    route = factory.SubFactory(RouteFactory)
    user = factory.SubFactory(UserFactory)
