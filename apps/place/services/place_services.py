from django.db.models import Count, QuerySet

from apps.place.models import Place


def get_place_list() -> QuerySet[Place]:
    queryset = Place.objects.prefetch_related("images", "tags").annotate(bookmark_count=Count("bookmarks"))
    return queryset
