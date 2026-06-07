from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.travel_quiz.schemas.travel_quiz_schemas import quiz_submit_schema
from apps.travel_quiz.serializers.travel_quiz_serializers import (
    QuizSubmitResponseSerializer,
    QuizSubmitSerializer,
)
from apps.travel_quiz.services.travel_quiz_services import submit_quiz


class QuizSubmitView(APIView):
    permission_classes = [AllowAny]

    @quiz_submit_schema
    def post(self, request: Request) -> Response:
        serializer = QuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = submit_quiz(user=request.user, answers=serializer.validated_data["answers"])
        return Response(QuizSubmitResponseSerializer(result).data, status=status.HTTP_200_OK)
