from rest_framework import status
from rest_framework.exceptions import APIException


class PlaceNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "존재하지 않는 장소입니다."


class ReviewNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "존재하지 않는 리뷰입니다."


class AlreadyReviewed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "이미 리뷰를 작성한 장소입니다."


class ForbiddenReviewEdit(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "본인이 작성한 리뷰만 수정할 수 있습니다."


class ForbiddenReviewDelete(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "본인이 작성한 리뷰만 삭제할 수 있습니다."


class RouteNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "존재하지 않는 경로입니다."


class RouteNotIncluded(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "선택한 경로에 해당 장소가 포함되어 있지 않습니다."
