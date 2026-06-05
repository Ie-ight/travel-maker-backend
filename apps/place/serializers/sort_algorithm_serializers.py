from rest_framework import serializers


class SortAlgorithmRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    # TODO: define fields after receiving place data spec from team
    # expected: user_vector (list[float]), tag_ids (list[int], optional), region_tag_id (int, optional)
    pass


class SortAlgorithmResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    # TODO: define output fields
    pass
