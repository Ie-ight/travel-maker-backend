from drf_spectacular.utils import extend_schema

from apps.travel_quiz.serializers.travel_quiz_serializers import (
    AvatarUpdateResponseSerializer,
    AvatarUpdateSerializer,
    QuizErrorResponseSerializer,
    QuizResultSerializer,
    QuizSubmitResponseSerializer,
    QuizSubmitSerializer,
)

quiz_submit_schema = extend_schema(
    tags=["TravelQuiz"],
    summary="여행 성향 테스트 제출",
    description=(
        "12개의 A/B 답변을 제출해 6축 점수를 계산하고 8가지 여행 유형 중 하나를 결정합니다. "
        "로그인 유저는 결과가 자동 저장되며, 게스트는 결과만 반환됩니다."
    ),
    request=QuizSubmitSerializer,
    responses={
        200: QuizSubmitResponseSerializer,
        400: QuizErrorResponseSerializer,
    },
)

quiz_result_schema = extend_schema(
    tags=["TravelQuiz"],
    summary="내 퀴즈 결과 조회",
    description="로그인한 유저의 여행 성향 테스트 결과(마이페이지)를 조회합니다.",
    responses={
        200: QuizResultSerializer,
        401: QuizErrorResponseSerializer,
        404: QuizErrorResponseSerializer,
    },
)

quiz_avatar_schema = extend_schema(
    tags=["TravelQuiz"],
    summary="퀴즈 결과 캐릭터를 프로필 이미지로 등록",
    description="travel_type_id로 지정한 여행 성향 캐릭터의 이미지를 로그인한 유저의 프로필 이미지로 등록합니다.",
    request=AvatarUpdateSerializer,
    responses={
        200: AvatarUpdateResponseSerializer,
        400: QuizErrorResponseSerializer,
        401: QuizErrorResponseSerializer,
    },
)
