from typing import cast

from rest_framework import serializers

from apps.place.models import Place
from apps.travel_quiz.exceptions import InvalidAnswerChoice, InvalidAnswersLength
from apps.travel_quiz.models import TravelType, UserTestResult
from apps.travel_quiz.services.travel_quiz_services import (
    QuizSubmitResult,
    build_type_tags,
    calculate_match_rate,
    get_recommended_places,
    label_vector,
    make_description,
)

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
    match_rate = serializers.SerializerMethodField()

    def get_image_url(self, obj: Place) -> str | None:
        image = obj.images.filter(is_main=True).first()
        return image.image_url if image else None

    def get_tags(self, obj: Place) -> list[str]:
        return list(obj.tags.values_list("tag_name", flat=True))

    def get_style_vector(self, obj: Place) -> list[dict[str, object]]:
        return label_vector([float(v) for v in obj.place_feature.style_vector])

    def get_match_rate(self, obj: Place) -> int:
        return calculate_match_rate(obj)

    class Meta:
        model = Place
        fields = ["place_id", "place_name", "description", "image_url", "tags", "style_vector", "match_rate"]


class PlaceMatchSerializer(serializers.ModelSerializer[Place]):
    """QuizResultSerializer.destinations용 최소 정보 (이름 + 매칭률만)."""

    place_id = serializers.IntegerField(source="id")
    match_rate = serializers.SerializerMethodField()

    def get_match_rate(self, obj: Place) -> int:
        return calculate_match_rate(obj)

    class Meta:
        model = Place
        fields = ["place_id", "place_name", "match_rate"]


class DetailCardSerializer(serializers.Serializer):  # type: ignore[type-arg]
    title = serializers.CharField()
    description = serializers.CharField()


class TravelTypeBriefSerializer(serializers.ModelSerializer[TravelType]):
    travel_type_id = serializers.IntegerField(source="id")
    type_tags = serializers.SerializerMethodField()

    def get_type_tags(self, obj: TravelType) -> list[str]:
        return build_type_tags(obj.type_key)

    class Meta:
        model = TravelType
        fields = ["travel_type_id", "type_key", "type_tags", "name", "image_url"]


class QuizSubmitResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    saved = serializers.BooleanField()
    travel_type_id = serializers.IntegerField(source="travel_type.id")
    type_key = serializers.CharField(source="travel_type.type_key")
    name = serializers.CharField(source="travel_type.name")
    description = serializers.CharField()
    image_url = serializers.CharField(source="travel_type.image_url")
    type_tags = serializers.ListField(child=serializers.CharField())
    detail_cards = DetailCardSerializer(many=True)
    result_vector = serializers.SerializerMethodField()
    compatible_type = TravelTypeBriefSerializer()
    incompatible_type = TravelTypeBriefSerializer()
    destinations = PlaceRecommendationSerializer(source="recommended_places", many=True)

    def get_result_vector(self, obj: QuizSubmitResult) -> list[dict[str, object]]:
        return label_vector(obj.result_vector)


class QuizResultSerializer(serializers.Serializer):  # type: ignore[type-arg]
    type_key = serializers.CharField(source="travel_type.type_key")
    name = serializers.CharField(source="travel_type.name")
    description = serializers.SerializerMethodField()
    image_url = serializers.CharField(source="travel_type.image_url")
    type_tags = serializers.SerializerMethodField()
    result_vector = serializers.SerializerMethodField()
    destinations = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField()

    def get_description(self, obj: UserTestResult) -> str:
        return make_description(obj.result_vector)

    def get_type_tags(self, obj: UserTestResult) -> list[str]:
        return build_type_tags(obj.travel_type.type_key)

    def get_result_vector(self, obj: UserTestResult) -> list[dict[str, object]]:
        return label_vector(obj.result_vector)

    def get_destinations(self, obj: UserTestResult) -> list[dict[str, object]]:
        places = get_recommended_places(obj.result_vector)
        return cast(list[dict[str, object]], PlaceMatchSerializer(places, many=True).data)


class AvatarUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    travel_type_id = serializers.IntegerField(required=True)


class AvatarUpdateResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    updated = serializers.BooleanField()


class QuizErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    error_detail = serializers.CharField()
