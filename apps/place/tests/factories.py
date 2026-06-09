import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.place.models import Place, PlaceImage, Tag

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"u{n}@test.com")
    nickname = factory.Sequence(lambda n: f"u_{n:04d}")
    gender = "M"
    birthday = "2000-01-01"
    is_active = True


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    tag_type = "분위기"
    tag_name = factory.Sequence(lambda n: f"tag{n}")


class PlaceFactory(DjangoModelFactory):
    class Meta:
        model = Place
        skip_postgeneration_save = True

    place_name = factory.Sequence(lambda n: f"place{n}")
    latitude = "37.1234567"
    longitude = "127.1234567"
    content_id = factory.Sequence(lambda n: n + 1)
    content_type_id = 12

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
        PlaceImageFactory.create_batch(2, place=self)

    @factory.post_generation
    def tags(self, create: bool, extracted: list[Tag] | None, **kwargs: object) -> None:
        if not create:
            return
        if extracted is not None:
            self.tags.set(extracted)
            return
        self.tags.add(*TagFactory.create_batch(2))


class PlaceImageFactory(DjangoModelFactory):
    class Meta:
        model = PlaceImage

    place = factory.SubFactory(PlaceFactory)
    image_url = factory.Sequence(lambda n: f"image{n}.jpg")
    is_main = False
    order = factory.Sequence(lambda n: n)
