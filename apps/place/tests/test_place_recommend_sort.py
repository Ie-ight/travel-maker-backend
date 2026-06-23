import pytest
from django.core.cache import cache

from apps.place.models import Place, PlaceFeature
from apps.place.services.feed_stage_service import determine_stage
from apps.place.services.place_services import get_place_list_recommend
from apps.place.tests.factories import PlaceFactory, UserFactory
from apps.travel_quiz.tests.factories import UserTestResultFactory
from apps.user.models import UserPreference
from apps.user.services import behavior_constants


def _make_place(content_id: int, style_vector: list[float], content_vector: list[float] | None = None) -> Place:
    place = PlaceFactory(content_id=content_id)
    PlaceFeature.objects.create(place=place, style_vector=style_vector, content_vector=content_vector)
    return place


@pytest.mark.django_db
class TestDetermineStage:
    def test_비로그인은_S1(self) -> None:
        assert determine_stage(None) == "S1"

    def test_퀴즈결과없고_행동없으면_S1(self) -> None:
        user = UserFactory()
        assert determine_stage(user.id) == "S1"

    def test_퀴즈결과있고_action_count_threshold_미달이면_S2(self) -> None:
        user = UserFactory()
        UserTestResultFactory(user=user)
        UserPreference.objects.create(user=user, action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD - 1)

        assert determine_stage(user.id) == "S2"

    def test_action_count_threshold_이상이고_content_vector_있으면_S3(self) -> None:
        user = UserFactory()
        UserTestResultFactory(user=user)
        UserPreference.objects.create(
            user=user,
            action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD,
            content_vector=[1.0] + [0.0] * 1023,
        )

        assert determine_stage(user.id) == "S3"

    def test_action_count_threshold_이상이지만_content_vector_없으면_S2로_폴백(self) -> None:
        user = UserFactory()
        UserTestResultFactory(user=user)
        UserPreference.objects.create(user=user, action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD)

        assert determine_stage(user.id) == "S2"

    def test_action_count_threshold_이상_퀴즈결과없으면_S1(self) -> None:
        user = UserFactory()
        UserPreference.objects.create(user=user, action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD)

        assert determine_stage(user.id) == "S1"


@pytest.mark.django_db
class TestGetPlaceListRecommendStages:
    def test_S1_비로그인은_인기순_폴백(self) -> None:
        cache.clear()
        place1 = _make_place(1, [0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
        place2 = _make_place(2, [0.9, 0.9, 0.9, 0.9, 0.9, 0.9])

        places = get_place_list_recommend(user_id=None)

        assert {p.id for p in places} == {place1.id, place2.id}

    def test_S2_퀴즈_6축_ANN_정렬(self) -> None:
        user = UserFactory()
        UserTestResultFactory(user=user, result_vector=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        near = _make_place(11, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        far = _make_place(12, [0.0, 0.0, 0.0, 0.0, 0.0, 1.0])

        assert determine_stage(user.id) == "S2"

        places = list(get_place_list_recommend(user_id=user.id))

        place_ids = [p.id for p in places]
        assert place_ids.index(near.id) < place_ids.index(far.id)

    def test_S3_행동기반_임베딩_ANN_정렬(self) -> None:
        user = UserFactory()
        UserTestResultFactory(user=user)

        near = _make_place(21, [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], content_vector=[1.0] + [0.0] * 1023)
        far = _make_place(22, [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], content_vector=[0.0, 1.0] + [0.0] * 1022)

        UserPreference.objects.create(
            user=user,
            action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD,
            content_vector=[1.0] + [0.0] * 1023,
        )

        assert determine_stage(user.id) == "S3"

        places = list(get_place_list_recommend(user_id=user.id))

        place_ids = [p.id for p in places]
        assert place_ids.index(near.id) < place_ids.index(far.id)

    def test_content_vector_없는_장소는_S3_결과_하단에_포함(self) -> None:
        user = UserFactory()
        UserTestResultFactory(user=user)

        with_vector = _make_place(31, [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], content_vector=[1.0] + [0.0] * 1023)
        without_vector = _make_place(32, [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], content_vector=None)

        UserPreference.objects.create(
            user=user,
            action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD,
            content_vector=[1.0] + [0.0] * 1023,
        )

        places = list(get_place_list_recommend(user_id=user.id))

        place_ids = [p.id for p in places]
        # 벡터 있는 장소는 상단, 없는 장소는 하단(인기순)에 포함
        assert with_vector.id in place_ids
        assert without_vector.id in place_ids
        assert place_ids.index(with_vector.id) < place_ids.index(without_vector.id)

    def test_단계전환_경계_action_count_9는_S2_10은_S3(self) -> None:
        user = UserFactory()
        UserTestResultFactory(user=user, result_vector=[0.0, 0.0, 0.0, 0.0, 0.0, 1.0])

        style_near = _make_place(41, [0.0, 0.0, 0.0, 0.0, 0.0, 1.0], content_vector=[0.0, 1.0] + [0.0] * 1022)
        content_near = _make_place(42, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], content_vector=[1.0] + [0.0] * 1023)

        preference = UserPreference.objects.create(
            user=user,
            action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD - 1,
            content_vector=[1.0] + [0.0] * 1023,
        )
        assert determine_stage(user.id) == "S2"
        s2_places = [p.id for p in get_place_list_recommend(user_id=user.id)]
        assert s2_places.index(style_near.id) < s2_places.index(content_near.id)

        preference.action_count = behavior_constants.S3_ACTION_COUNT_THRESHOLD
        preference.save(update_fields=["action_count"])
        assert determine_stage(user.id) == "S3"
        s3_places = [p.id for p in get_place_list_recommend(user_id=user.id)]
        assert s3_places.index(content_near.id) < s3_places.index(style_near.id)

    def test_태그_필터에서도_S3_분기가_동작한다(self) -> None:
        from apps.place.tests.factories import TagFactory

        user = UserFactory()
        UserTestResultFactory(user=user)
        tag = TagFactory()

        place = _make_place(51, [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], content_vector=[1.0] + [0.0] * 1023)
        place.tags.add(tag)

        UserPreference.objects.create(
            user=user,
            action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD,
            content_vector=[1.0] + [0.0] * 1023,
        )

        places = list(get_place_list_recommend(user_id=user.id, tags=[tag.id]))

        assert place.id in {p.id for p in places}
