from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apps.share.serializers.share_serializers import ShareRequestSerializer, ShareResponseSerializer

share_create_schema = extend_schema(
    summary="공유 URL 생성",
    description=(
        "content_type과 content_id를 받아 공유 URL을 반환합니다.\n\n"
        "## content_type별 동작\n\n"
        "### place\n"
        "`content_id`(장소 ID)를 넘기면 장소 상세 페이지 URL을 반환합니다.\n\n"
        "### route\n"
        "`content_id`(경로 ID)를 넘기면 여행 경로 상세 페이지 URL을 반환합니다.\n\n"
        "### travel_quiz\n"
        "성향 테스트 결과를 공유합니다. `type_key`와 6차원 `vector`가 쿼리스트링에 포함된 URL을 반환합니다.\n\n"
        "로그인 상태에 따라 요청 방식이 다릅니다:\n\n"
        "| 구분 | 필요 필드 | 동작 |\n"
        "|------|-----------|------|\n"
        "| **로그인 유저** | `content_id` (유저 ID) | DB에 저장된 결과를 조회하여 URL 생성 |\n"
        "| **비로그인 유저** | `type_key` + `vector` | 퀴즈 제출 응답의 `type_key`, `raw_vector`를 그대로 전달 |\n\n"
        "> 비로그인 유저는 퀴즈 제출(`POST /api/v1/quiz/submit`) 응답의 `type_key`와 `raw_vector` 필드를 "
        "그대로 사용하면 됩니다."
    ),
    request=ShareRequestSerializer,
    examples=[
        OpenApiExample(
            "장소 공유",
            value={"content_type": "place", "content_id": 1},
            request_only=True,
        ),
        OpenApiExample(
            "경로 공유",
            value={"content_type": "route", "content_id": 42},
            request_only=True,
        ),
        OpenApiExample(
            "성향 테스트 공유 - 로그인 유저",
            value={"content_type": "travel_quiz", "content_id": 7},
            request_only=True,
        ),
        OpenApiExample(
            "성향 테스트 공유 - 비로그인 유저",
            value={
                "content_type": "travel_quiz",
                "type_key": "ENF",
                "vector": [0.8, 0.6, 0.4, 0.3, 0.7, 0.5],
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=ShareResponseSerializer,
            description="공유 URL 생성 성공",
            examples=[
                OpenApiExample(
                    "장소 공유",
                    value={"share_url": "http://localhost:3000/place/1"},
                ),
                OpenApiExample(
                    "경로 공유",
                    value={"share_url": "http://localhost:3000/route/42"},
                ),
                OpenApiExample(
                    "성향 테스트 공유 - 로그인 유저 (content_id 사용)",
                    value={
                        "share_url": "http://localhost:3000/quiz/result?type_key=ENF&vector=0.8,0.6,0.4,0.3,0.7,0.5"
                    },
                    request_only=False,
                ),
                OpenApiExample(
                    "성향 테스트 공유 - 비로그인 유저 (type_key + vector 직접 전달)",
                    value={
                        "share_url": "http://localhost:3000/quiz/result?type_key=ENF&vector=0.8,0.6,0.4,0.3,0.7,0.5"
                    },
                    request_only=False,
                ),
            ],
        ),
        400: OpenApiResponse(
            description="잘못된 요청",
            examples=[
                OpenApiExample(
                    "travel_quiz 필수 필드 누락",
                    value={
                        "error_detail": "travel_quiz 공유는 content_id 또는 type_key와 vector를 함께 입력해야 합니다."
                    },
                ),
            ],
        ),
        404: OpenApiResponse(
            description="콘텐츠를 찾을 수 없음",
            examples=[
                OpenApiExample(
                    "장소 없음",
                    value={"error_detail": "장소를 찾을 수 없습니다."},
                ),
                OpenApiExample(
                    "경로 없음",
                    value={"error_detail": "경로를 찾을 수 없습니다."},
                ),
                OpenApiExample(
                    "테스트 결과 없음",
                    value={"error_detail": "해당 유저의 테스트 결과를 찾을 수 없습니다."},
                ),
            ],
        ),
    },
    tags=["share"],
)
