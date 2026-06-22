from typing import Never, cast

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.travel_quiz.schemas.travel_quiz_schemas import (
    quiz_avatar_schema,
    quiz_result_schema,
    quiz_shared_result_schema,
    quiz_submit_schema,
)
from apps.travel_quiz.serializers.travel_quiz_serializers import (
    AvatarUpdateResponseSerializer,
    AvatarUpdateSerializer,
    QuizResultSerializer,
    QuizSubmitResponseSerializer,
    QuizSubmitSerializer,
    SharedQuizRequestSerializer,
    SharedQuizResultSerializer,
)
from apps.travel_quiz.services.travel_quiz_services import (
    get_shared_quiz_result,
    get_user_quiz_result,
    submit_quiz,
    update_user_avatar,
)
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


class SharedQuizResultView(APIView):
    permission_classes = [AllowAny]

    @quiz_shared_result_schema
    def get(self, request: Request) -> Response:
        serializer = SharedQuizRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = get_shared_quiz_result(
            type_key=serializer.validated_data["type_key"],
            norm=serializer.validated_data["vector"],
        )
        return Response(SharedQuizResultSerializer(result).data, status=status.HTTP_200_OK)


class QuizAvatarView(APIView):
    permission_classes = [IsAuthenticated]

    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> Never:
        raise NotAuthenticated("자격 인증 데이터가 제공되지 않았습니다.")

    @quiz_avatar_schema
    def patch(self, request: Request) -> Response:
        serializer = AvatarUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = update_user_avatar(cast(User, request.user), serializer.validated_data["travel_type_id"])
        return Response(AvatarUpdateResponseSerializer({"updated": updated}).data, status=status.HTTP_200_OK)
