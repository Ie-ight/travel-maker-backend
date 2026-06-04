from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.place.serializers.place_serializers import PlaceErrorResponseSerializer
from apps.review.serializers.review_serializers import (
    ReviewCreateResponseSerializer,
    ReviewCreateSerializer,
    ReviewListItemSerializer,
    ReviewUpdateResponseSerializer,
    ReviewUpdateSerializer,
)

review_list_schema = extend_schema(
    tags=["Review"],
    summary="리뷰 목록 조회",
    parameters=[
        OpenApiParameter(name="page", type=int, description="페이지 번호"),
        OpenApiParameter(name="page_size", type=int, description="목록 출력 개수: 기본 4"),
    ],
    responses={200: ReviewListItemSerializer, 404: PlaceErrorResponseSerializer},
)

review_create_schema = extend_schema(
    tags=["Review"],
    summary="리뷰 등록",
    description="장소에 리뷰를 등록합니다. 이미지는 비동기로 S3에 업로드됩니다.",
    request={"multipart/form-data": ReviewCreateSerializer},
    responses={
        201: ReviewCreateResponseSerializer,
        400: PlaceErrorResponseSerializer,
        401: PlaceErrorResponseSerializer,
        409: PlaceErrorResponseSerializer,
    },
)

review_update_schema = extend_schema(
    tags=["Review"],
    summary="리뷰 수정",
    request=ReviewUpdateSerializer,
    responses={
        200: ReviewUpdateResponseSerializer,
        400: PlaceErrorResponseSerializer,
        401: PlaceErrorResponseSerializer,
        403: PlaceErrorResponseSerializer,
        404: PlaceErrorResponseSerializer,
    },
)

review_delete_schema = extend_schema(
    tags=["Review"],
    summary="리뷰 삭제",
    responses={
        204: None,
        401: PlaceErrorResponseSerializer,
        403: PlaceErrorResponseSerializer,
        404: PlaceErrorResponseSerializer,
    },
)
