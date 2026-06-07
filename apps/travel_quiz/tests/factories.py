import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.place.models import Place, PlaceImage, Tag
from apps.travel_quiz.models import TravelType, UserTestResult

User = get_user_model()


class UserFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"u{n}@test.com")  # type: ignore[misc]
    nickname = factory.Sequence(lambda n: f"u_{n:04d}")  # type: ignore[misc]
    gender = "M"
    birthday = "2000-01-01"
    is_active = True


class TagFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Tag

    tag_type = "여행 스타일"
    tag_name = factory.Sequence(lambda n: f"tag{n}")  # type: ignore[misc]


class TravelTypeFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = TravelType
        skip_postgeneration_save = True

    type_key = factory.Sequence(lambda n: f"k{n:02d}")  # type: ignore[misc]
    name = factory.Sequence(lambda n: f"여행유형{n}")  # type: ignore[misc]
    description = factory.Sequence(lambda n: f"한 줄 설명 {n}")  # type: ignore[misc]
    image_url = "https://example.com/travel-type.png"

    @factory.post_generation
    def tags(self, create: bool, extracted: list[Tag] | None, **kwargs: object) -> None:
        if not create:
            return
        if extracted is not None:
            self.tags.set(extracted)
            return
        self.tags.add(*TagFactory.create_batch(2))


class UserTestResultFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = UserTestResult

    user = factory.SubFactory(UserFactory)  # type: ignore[misc]
    travel_type = factory.SubFactory(TravelTypeFactory)  # type: ignore[misc]
    result_vector = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]


class PlaceFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Place
        skip_postgeneration_save = True

    place_name = factory.Sequence(lambda n: f"place{n}")  # type: ignore[misc]
    description = factory.Sequence(lambda n: f"장소 설명 {n}")  # type: ignore[misc]
    content_id = factory.Sequence(lambda n: n + 1)  # type: ignore[misc]
    content_type_id = 12
    is_active = True

    @factory.post_generation
    def images(self, create: bool, extracted: list[PlaceImage] | None, **kwargs: object) -> None:
        if not create:
            return
        if extracted is not None:
            for image in extracted:
                image.place = self
                image.save()
            return
        PlaceImageFactory(place=self, is_main=True, order=0, image_url="main.jpg")

    @factory.post_generation
    def tags(self, create: bool, extracted: list[Tag] | None, **kwargs: object) -> None:
        if not create:
            return
        if extracted is not None:
            self.tags.set(extracted)
            return
        self.tags.add(*TagFactory.create_batch(2))


class PlaceImageFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = PlaceImage

    place = factory.SubFactory(PlaceFactory)  # type: ignore[misc]
    image_url = factory.Sequence(lambda n: f"image{n}.jpg")  # type: ignore[misc]
    is_main = False
    order = factory.Sequence(lambda n: n)  # type: ignore[misc]
