from rest_framework import serializers

from apps.place.models import Place
from apps.travel_quiz.exceptions import InvalidAnswerChoice, InvalidAnswersLength
from apps.travel_quiz.models import UserTestResult
from apps.travel_quiz.services.travel_quiz_services import build_type_tags, make_description

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
    style_vector = serializers.SerializerMethodField()

    def get_image_url(self, obj: Place) -> str | None:
        image = obj.images.filter(is_main=True).first()
        return image.image_url if image else None

    def get_tags(self, obj: Place) -> list[str]:
        return list(obj.tags.values_list("tag_name", flat=True))

    def get_style_vector(self, obj: Place) -> list[float]:
        return [round(float(v), 2) for v in obj.place_feature.style_vector]

    class Meta:
        model = Place
        fields = ["place_id", "place_name", "description", "image_url", "tags", "style_vector"]


class DetailCardSerializer(serializers.Serializer):  # type: ignore[type-arg]
    title = serializers.CharField()
    description = serializers.CharField()


class QuizSubmitResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    saved = serializers.BooleanField()
    travel_type_id = serializers.IntegerField(source="travel_type.id")
    type_key = serializers.CharField(source="travel_type.type_key")
    name = serializers.CharField(source="travel_type.name")
    description = serializers.CharField()
    image_url = serializers.CharField(source="travel_type.image_url")
    type_tags = serializers.ListField(child=serializers.CharField())
    detail_cards = DetailCardSerializer(many=True)
    result_vector = serializers.ListField(child=serializers.FloatField())
    destinations = PlaceRecommendationSerializer(source="recommended_places", many=True)


class QuizResultSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(source="travel_type.name")
    description = serializers.SerializerMethodField()
    image_url = serializers.CharField(source="travel_type.image_url")
    type_tags = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField()

    def get_description(self, obj: UserTestResult) -> str:
        return make_description(obj.result_vector)

    def get_type_tags(self, obj: UserTestResult) -> list[str]:
        return build_type_tags(obj.travel_type.type_key)


class AvatarUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    travel_type_id = serializers.IntegerField(required=True)


class AvatarUpdateResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    updated = serializers.BooleanField()


class QuizErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error_detail = serializers.CharField()
