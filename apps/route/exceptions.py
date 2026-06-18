from rest_framework import status
from rest_framework.exceptions import APIException


class RouteNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "존재하지 않는 경로입니다."
    default_code = "not_found"


class RouteForbidden(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "권한이 없습니다."
    default_code = "forbidden"


class RouteValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "잘못된 요청입니다."
    default_code = "invalid"
