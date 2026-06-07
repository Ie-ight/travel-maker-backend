from drf_spectacular.utils import extend_schema

from apps.travel_quiz.serializers.travel_quiz_serializers import (
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
