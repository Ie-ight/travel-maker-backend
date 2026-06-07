from typing import Never, cast

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.travel_quiz.schemas.travel_quiz_schemas import quiz_result_schema, quiz_submit_schema
from apps.travel_quiz.serializers.travel_quiz_serializers import (
    QuizResultSerializer,
    QuizSubmitResponseSerializer,
    QuizSubmitSerializer,
)
from apps.travel_quiz.services.travel_quiz_services import get_user_quiz_result, submit_quiz
from apps.user.models import User


class QuizSubmitView(APIView):
    permission_classes = [AllowAny]

    @quiz_submit_schema
    def post(self, request: Request) -> Response:
        serializer = QuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = submit_quiz(user=request.user, answers=serializer.validated_data["answers"])
        return Response(QuizSubmitResponseSerializer(result).data, status=status.HTTP_200_OK)


class QuizResultView(APIView):
    permission_classes = [IsAuthenticated]

    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> Never:
        raise NotAuthenticated("자격 인증 데이터가 제공되지 않았습니다.")

    @quiz_result_schema
    def get(self, request: Request) -> Response:
        result = get_user_quiz_result(cast(User, request.user))
        return Response(QuizResultSerializer(result).data, status=status.HTTP_200_OK)
