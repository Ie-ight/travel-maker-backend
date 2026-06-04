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
