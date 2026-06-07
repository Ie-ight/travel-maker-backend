from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidAnswersLength(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "answers 길이가 12여야 합니다."


class InvalidAnswerChoice(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "answers 각 항목은 'A' 또는 'B'여야 합니다."


class QuizResultNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "퀴즈 결과를 찾을 수 없습니다."
