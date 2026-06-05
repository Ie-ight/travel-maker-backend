from django.db.models import QuerySet

from apps.place.models import PlaceFeature


def get_places_sorted_by_vector(
    user_vector: list[float],
    tag_ids: list[int] | None = None,
    region_tag_id: int | None = None,
    limit: int = 20,
) -> QuerySet[PlaceFeature]:
    # TODO: implement after receiving place data (location, vector, tags) from team
    raise NotImplementedError
