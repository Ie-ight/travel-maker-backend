from rest_framework import serializers

CONTENT_TYPE_CHOICES = ["place", "route", "travel_quiz"]


class ShareRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    content_type = serializers.ChoiceField(choices=CONTENT_TYPE_CHOICES)
    # place / route: 필수. travel_quiz: content_id(로그인) 또는 type_key+vector(비로그인) 중 택일.
    content_id = serializers.IntegerField(min_value=1, required=False)
    type_key = serializers.CharField(max_length=10, required=False)
    vector = serializers.ListField(
        child=serializers.FloatField(),
        min_length=6,
        max_length=6,
        required=False,
    )

    def validate(self, attrs: dict) -> dict:  # type: ignore[override]
        content_type = attrs.get("content_type")
        content_id = attrs.get("content_id")
        type_key = attrs.get("type_key")
        vector = attrs.get("vector")

        if content_type == "travel_quiz":
            has_db_path = content_id is not None
            has_direct_path = type_key is not None and vector is not None
            if not has_db_path and not has_direct_path:
                raise serializers.ValidationError(
                    "travel_quiz 공유는 content_id 또는 type_key와 vector를 함께 입력해야 합니다."
                )
        else:
            if content_id is None:
                raise serializers.ValidationError({"content_id": "이 필드는 필수입니다."})

        return attrs


class ShareResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    share_url = serializers.URLField()
