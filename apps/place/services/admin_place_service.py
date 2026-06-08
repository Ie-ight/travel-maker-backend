from django.db import transaction

from apps.core.exceptions import NotFound
from apps.place.models import Place, PlaceImage, Tag


@transaction.atomic
def admin_create_place(data: dict[str, object]) -> Place:
    tag_ids: list[int] = data.pop("tag_ids", [])  # type: ignore[assignment]
    image_urls: list[str] = data.pop("image_urls", [])  # type: ignore[assignment]
    place = Place.objects.create(**data)
    if tag_ids:
        place.tags.set(Tag.objects.filter(id__in=tag_ids))
    for i, url in enumerate(image_urls):
        PlaceImage.objects.create(place=place, image_url=url, is_main=(i == 0), order=i)
    return place


@transaction.atomic
def admin_update_place(place_id: int, data: dict[str, object]) -> Place:
    try:
        place = Place.objects.get(pk=place_id)
    except Place.DoesNotExist:
        raise NotFound("존재하지 않는 장소입니다.") from None
    tag_ids: list[int] | None = data.pop("tag_ids", None)  # type: ignore[assignment]
    image_urls: list[str] | None = data.pop("image_urls", None)  # type: ignore[assignment]
    for field, value in data.items():
        setattr(place, field, value)
    place.save()
    if tag_ids is not None:
        place.tags.set(Tag.objects.filter(id__in=tag_ids))
    if image_urls is not None:
        PlaceImage.objects.filter(place=place).delete()
        for i, url in enumerate(image_urls):
            PlaceImage.objects.create(place=place, image_url=url, is_main=(i == 0), order=i)
    return place


def admin_delete_place(place_id: int) -> None:
    try:
        place = Place.objects.get(pk=place_id)
    except Place.DoesNotExist:
        raise NotFound("존재하지 않는 장소입니다.") from None
    place.delete()
