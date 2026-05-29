from django.db.models import Count

from apps.place.models import Place


def get_place_list():
    queryset = Place.objects.prefetch_related("images", "tags").annotate(bookmark_count=Count("bookmarks"))
    return queryset
