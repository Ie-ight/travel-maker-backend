from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from apps.core.presigned_url.serializers import PresignedUrlRequestSerializer, PresignedUrlResponseSerializer
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
    description="장소에 등록된 리뷰 목록을 조회합니다.\n존재하지 않는 장소 ID면 404 에러가 발생합니다.",
    parameters=[
        OpenApiParameter(name="page", type=int, description="페이지 번호"),
        OpenApiParameter(name="page_size", type=int, description="목록 출력 개수: 기본 4"),
    ],
    responses={200: ReviewListItemSerializer, 404: PlaceErrorResponseSerializer},
)

review_create_schema = extend_schema(
    tags=["Review"],
    summary="리뷰 등록",
    description=(
        "장소에 리뷰를 등록합니다.\n"
        "이미지를 첨부하려면 presigned URL 발급 API로 받은 img_url을 image_url 필드에 담아 전달하세요.\n"
        "이 장소가 포함된 내 경로를 함께 보여주고 싶다면 해당 경로의 ID를 route_id로 전달하세요. "
        "본인 소유가 아니거나 존재하지 않는 경로면 404, 해당 장소가 포함되지 않은 경로면 400 에러가 발생합니다.\n"
        "rating은 1~5점 사이로 입력해야 하며, 존재하지 않는 장소면 404, "
        "이미 해당 장소에 리뷰를 작성한 경우 409 에러가 발생합니다."
    ),
    request=ReviewCreateSerializer,
    responses={
        201: ReviewCreateResponseSerializer,
        400: PlaceErrorResponseSerializer,
        401: PlaceErrorResponseSerializer,
        404: PlaceErrorResponseSerializer,
        409: PlaceErrorResponseSerializer,
    },
)

review_update_schema = extend_schema(
    tags=["Review"],
    summary="리뷰 수정",
    description=(
        "본인이 작성한 리뷰를 수정합니다. rating, content, image_url, route_id 중 최소 1개 이상 입력해야 합니다.\n"
        "route_id에 이 장소가 포함된 내 경로의 ID를 전달하면 리뷰에 연결되고, null을 전달하면 연결이 해제됩니다.\n"
        "본인이 작성한 리뷰가 아니면 403, 존재하지 않는 리뷰/경로면 404, "
        "선택한 경로에 이 장소가 포함되지 않으면 400 에러가 발생합니다."
    ),
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
    description=(
        "본인이 작성한 리뷰를 삭제합니다.\n본인이 작성한 리뷰가 아니면 403, 존재하지 않는 리뷰면 404 에러가 발생합니다."
    ),
    responses={
        204: None,
        401: PlaceErrorResponseSerializer,
        403: PlaceErrorResponseSerializer,
        404: PlaceErrorResponseSerializer,
    },
)

review_image_presigned_url_schema = extend_schema(
    tags=["Review"],
    summary="리뷰 이미지 업로드용 presigned URL 발급",
    description=(
        "리뷰에 첨부할 이미지를 S3에 직접 업로드할 수 있는 presigned URL을 발급합니다.\n"
        "응답으로 받은 img_url을 리뷰 등록/수정 요청의 image_url 필드에 담아 전달하세요."
    ),
    request=PresignedUrlRequestSerializer,
    responses={
        200: PresignedUrlResponseSerializer,
        400: OpenApiResponse(description="지원하지 않는 파일 형식입니다."),
        401: OpenApiResponse(description="자격 인증 데이터가 제공되지 않았습니다."),
    },
)
