from typing import cast

from django.core.cache import cache
from django.db.models import QuerySet

from apps.place.models import Tag


class TagService:
    @staticmethod
    def get_tags(tag_type: str | None = None) -> list[Tag]:
        cache_key = f"tags:{tag_type or 'all'}"
        cached = cast(list[Tag] | None, cache.get(cache_key))
        if cached is not None:
            return cached
        qs: QuerySet[Tag] = Tag.objects.all()
        if tag_type:
            qs = qs.filter(tag_type=tag_type)
        result = list(qs)
        cache.set(cache_key, result, 60 * 60 * 24)  # 24시간
        return result
