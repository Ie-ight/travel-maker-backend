# apps/core/exceptions.py

from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "이미 존재합니다."
    default_code = "conflict"


class NotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "찾을 수 없습니다."
    default_code = "not_found"


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "잘못된 요청입니다."
    default_code = "bad_request"
