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


class RouteAlreadyLiked(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "이미 좋아요한 경로입니다."
    default_code = "conflict"


class RouteLikeNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "좋아요 내역을 찾을 수 없습니다."
    default_code = "not_found"
