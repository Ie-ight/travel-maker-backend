import factory
from factory.django import DjangoModelFactory

from apps.place.models import Place, PlaceImage, Tag


class TagFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Tag

    tag_type = "분위기"
    tag_name = factory.Sequence(lambda n: f"tag{n}")  # type: ignore[misc]


class PlaceFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = Place
        skip_postgeneration_save = True

    place_name = factory.Sequence(lambda n: f"place{n}")  # type: ignore[misc]
    latitude = "37.1234567"
    longitude = "127.1234567"

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


class PlaceImageFactory(DjangoModelFactory):  # type: ignore[misc]
    class Meta:
        model = PlaceImage

    place = factory.SubFactory(PlaceFactory)  # type: ignore[misc]
    image_url = factory.Sequence(lambda n: f"image{n}.jpg")  # type: ignore[misc]
    is_main = False
    order = factory.Sequence(lambda n: n)  # type: ignore[misc]
