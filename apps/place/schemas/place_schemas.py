from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)

from apps.place.serializers.place_serializers import (
    PlaceDetailSerializer,
    PlaceErrorResponseSerializer,
    PlaceListResponseSerializer,
)

# 공통 장소 목록/검색 응답 예시 (재사용을 위해 변수 분리 가능하나 여기선 하드코딩)
LIST_SUCCESS_EXAMPLE = OpenApiExample(
    name="성공 예시",
    value={
        "count": 100,
        "next": "http://api.example.org/places/?page=2",
        "previous": None,
        "results": [
            {
                "id": 1,
                "place_name": "광안리 해수욕장",
                "image_url": "https://example.com/image1.jpg",
                "description": "부산을 대표하는 아름다운 해수욕장입니다.",
                "latitude": 35.1531696,
                "longitude": 129.118666,
                "bookmark_count": 150,
                "is_bookmarked": True,
                "rating_avg": 4.5,
                "tags": [
                    {"id": 1, "tag_name": "해변"},
                    {"id": 8, "tag_name": "해수욕·해안"},
                    {"id": 37, "tag_name": "부산"},
                ],
            }
        ],
    },
)

LIST_ERROR_EXAMPLE = OpenApiExample(
    name="에러 예시 (잘못된 페이지)", value={"error_detail": "유효하지 않은 페이지입니다."}
)

place_list_schema = extend_schema(
    tags=["Place"],
    summary="장소 목록 조회",
    description=(
        "현재 활성화된 장소 전체 목록을 페이징 처리하여 반환합니다.\n\n"
        "- 기본적으로 북마크 수가 많은 순(내림차순)으로 정렬됩니다.\n"
        "- 한 페이지당 기본 8개의 장소 데이터가 반환됩니다."
    ),
    parameters=[
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="페이지 번호 (예: 1). 0보다 작거나 없는 페이지를 요청하면 404 에러가 발생합니다.",
            default=1,
            examples=[OpenApiExample(name="1페이지 조회", value=1)],
        ),
        OpenApiParameter(
            name="page_size",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="목록 출력 개수. 기본 8, 최대 100",
            default=8,
            examples=[OpenApiExample(name="8개씩 출력", value=8)],
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PlaceListResponseSerializer, description="장소 목록 조회 성공", examples=[LIST_SUCCESS_EXAMPLE]
        ),
        404: OpenApiResponse(
            response=PlaceErrorResponseSerializer,
            description="유효하지 않은 페이지 요청",
            examples=[LIST_ERROR_EXAMPLE],
        ),
    },
)


place_search_schema = extend_schema(
    tags=["Place"],
    summary="장소 검색",
    description=(
        "키워드를 통해 장소명(place_name)을 부분 검색합니다.\n\n"
        "- 키워드가 주어지지 않으면 전체 목록을 반환합니다.\n"
        "- 정렬 기준(`sort`)과 정렬 방향(`order`)을 조합하여 결과를 정렬할 수 있습니다."
    ),
    parameters=[
        OpenApiParameter(
            name="keyword",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="장소명 부분 검색어. (예: '해수욕장')",
            required=False,
            examples=[OpenApiExample(name="해수욕장 검색", value="해수욕장")],
        ),
        OpenApiParameter(
            name="sort",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="정렬 기준. recommend 선택 시 order 파라미터는 무시됩니다.",
            enum=["bookmark", "review", "rating", "recommend"],
            default="bookmark",
            examples=[OpenApiExample(name="북마크순 정렬", value="bookmark")],
        ),
        OpenApiParameter(
            name="order",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="정렬 방향",
            enum=["desc", "asc"],
            default="desc",
            examples=[OpenApiExample(name="내림차순", value="desc")],
        ),
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="페이지 번호",
            default=1,
            examples=[OpenApiExample(name="1페이지 조회", value=1)],
        ),
        OpenApiParameter(
            name="page_size",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="목록 출력 개수 (최대 100)",
            default=8,
            examples=[OpenApiExample(name="8개씩 출력", value=8)],
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PlaceListResponseSerializer, description="장소 검색 성공", examples=[LIST_SUCCESS_EXAMPLE]
        ),
        404: OpenApiResponse(
            response=PlaceErrorResponseSerializer,
            description="유효하지 않은 페이지 요청",
            examples=[LIST_ERROR_EXAMPLE],
        ),
    },
)

place_filter_schema = extend_schema(
    tags=["Place"],
    summary="장소 태그 필터",
    description=(
        "태그 ID를 기반으로 장소를 필터링합니다.\n\n"
        "- 여러 개의 태그를 전달하면 해당 태그를 **모두 포함(AND)**한 장소만 반환합니다.\n"
        "- 예: `?tags=1&tags=3` (태그 1번과 3번을 모두 가진 장소 검색)"
    ),
    parameters=[
        OpenApiParameter(
            name="tags",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            many=True,
            description="필터링할 태그 ID 리스트 (AND 조건)",
            examples=[OpenApiExample(name="해변(1)과 부산(37) 동시 포함", value=[1, 37])],
        ),
        OpenApiParameter(
            name="keyword",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="장소명 부분 검색어",
            examples=[OpenApiExample(name="광안리 검색", value="광안리")],
        ),
        OpenApiParameter(
            name="sort",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="정렬 기준. recommend 선택 시 order 파라미터는 무시됩니다.",
            enum=["bookmark", "review", "rating", "recommend"],
            default="bookmark",
            examples=[OpenApiExample(name="평점순 정렬", value="rating")],
        ),
        OpenApiParameter(
            name="order",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="정렬 방향",
            enum=["desc", "asc"],
            default="desc",
            examples=[OpenApiExample(name="내림차순", value="desc")],
        ),
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="페이지 번호",
            default=1,
            examples=[OpenApiExample(name="1페이지 조회", value=1)],
        ),
        OpenApiParameter(
            name="page_size",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="목록 출력 개수",
            default=8,
            examples=[OpenApiExample(name="8개씩 출력", value=8)],
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PlaceListResponseSerializer, description="장소 필터링 성공", examples=[LIST_SUCCESS_EXAMPLE]
        ),
        404: OpenApiResponse(
            response=PlaceErrorResponseSerializer,
            description="유효하지 않은 페이지 요청",
            examples=[LIST_ERROR_EXAMPLE],
        ),
    },
)

place_detail_schema = extend_schema(
    tags=["Place"],
    summary="장소 상세 조회",
    description=(
        "고유 ID를 사용하여 장소의 상세 정보를 조회합니다.\n\n"
        "- 장소의 기본 정보뿐만 아니라 연관된 태그 정보 등이 포함됩니다."
    ),
    responses={
        200: OpenApiResponse(
            response=PlaceDetailSerializer,
            description="장소 상세 조회 성공",
            examples=[
                OpenApiExample(
                    name="성공 예시",
                    value={
                        "id": 125,
                        "place_name": "광안리 해수욕장",
                        "description": "부산의 랜드마크",
                        "latitude": 35.1531696,
                        "longitude": 129.118666,
                        "homepage": "http://gwangalli.kr",
                        "tel": "051-622-4251",
                        "address_primary": "부산광역시 수영구 광안해변로 219",
                        "address_detail": "1층",
                        "rating_avg": 4.8,
                        "review_count": 150,
                        "is_bookmarked": True,
                        "images": ["https://example.com/image_main.jpg", "https://example.com/image_sub.jpg"],
                        "tags": [
                            {"id": 1, "tag_name": "해변"},
                            {"id": 8, "tag_name": "해수욕·해안"},
                            {"id": 37, "tag_name": "부산"},
                        ],
                        "info": {
                            "operating_hours": "09:00~18:00",
                            "closed_days": "연중무휴",
                            "parking": True,
                            "admission_fee": False,
                            "spend_time": "약 2시간",
                            "discount_info": "장애인 무료",
                            "accom_count": "1000명",
                            "pet": True,
                            "baby_carriage": True,
                            "credit_card": True,
                        },
                    },
                )
            ],
        ),
        404: OpenApiResponse(
            response=PlaceErrorResponseSerializer,
            description="장소를 찾을 수 없음",
            examples=[
                OpenApiExample(name="에러 예시 (존재하지 않는 ID)", value={"error_detail": "존재하지 않는 장소입니다."})
            ],
        ),
    },
)
