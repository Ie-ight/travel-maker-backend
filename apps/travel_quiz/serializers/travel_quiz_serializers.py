from rest_framework import serializers

from apps.place.models import Place
from apps.travel_quiz.exceptions import InvalidAnswerChoice, InvalidAnswersLength
from apps.travel_quiz.services.travel_quiz_services import QuizSubmitResult

_VALID_CHOICES = {"A", "B"}


class QuizSubmitSerializer(serializers.Serializer):  # type: ignore[type-arg]
    answers = serializers.ListField(child=serializers.CharField())

    def validate_answers(self, value: list[str]) -> list[str]:
        if len(value) != 12:
            raise InvalidAnswersLength()
        normalized = [answer.upper() for answer in value]
        if any(answer not in _VALID_CHOICES for answer in normalized):
            raise InvalidAnswerChoice()
        return normalized


class PlaceRecommendationSerializer(serializers.ModelSerializer[Place]):
    place_id = serializers.IntegerField(source="id")
    image_url = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    def get_image_url(self, obj: Place) -> str | None:
        image = obj.images.filter(is_main=True).first()
        return image.image_url if image else None

    def get_tags(self, obj: Place) -> list[str]:
        return list(obj.tags.values_list("tag_name", flat=True))

    class Meta:
        model = Place
        fields = ["place_id", "place_name", "description", "image_url", "tags"]


class QuizSubmitResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    saved = serializers.BooleanField()
    travel_type_id = serializers.IntegerField(source="travel_type.id")
    type_key = serializers.CharField(source="travel_type.type_key")
    name = serializers.CharField(source="travel_type.name")
    description = serializers.CharField(source="travel_type.description")
    dynamic_description = serializers.CharField()
    image_url = serializers.CharField(source="travel_type.image_url")
    tags = serializers.SerializerMethodField()
    result_vector = serializers.ListField(child=serializers.FloatField())
    destinations = PlaceRecommendationSerializer(source="recommended_places", many=True)

    def get_tags(self, obj: QuizSubmitResult) -> list[str]:
        return list(obj.travel_type.tags.values_list("tag_name", flat=True))


class QuizErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error_detail = serializers.CharField()
