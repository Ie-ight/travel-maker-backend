from django.db.models import QuerySet

from apps.place.models import Tag


class TagService:
    @staticmethod
    def get_tags(tag_type: str | None = None) -> QuerySet[Tag]:
        qs: QuerySet[Tag] = Tag.objects.all()
        if tag_type:
            qs = qs.filter(tag_type=tag_type)
        return qs
