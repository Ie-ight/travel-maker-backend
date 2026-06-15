from drf_spectacular.utils import OpenApiExample, extend_schema

from apps.travel_quiz.serializers.travel_quiz_serializers import (
    AvatarUpdateResponseSerializer,
    AvatarUpdateSerializer,
    QuizErrorResponseSerializer,
    QuizResultSerializer,
    QuizSubmitResponseSerializer,
    QuizSubmitSerializer,
)

quiz_submit_schema = extend_schema(
    tags=["TravelQuiz"],
    summary="여행 성향 테스트 제출",
    description=(
        "12개의 A/B 답변을 제출해 6축 점수를 계산하고 8가지 여행 유형 중 하나를 결정합니다. "
        "로그인 유저는 결과가 자동 저장되며, 게스트는 결과만 반환됩니다."
    ),
    request=QuizSubmitSerializer,
    examples=[
        OpenApiExample(
            "12문항 답변 예시",
            value={"answers": ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B", "A", "B"]},
            request_only=True,
        ),
        OpenApiExample(
            "퀴즈 제출 응답",
            value={
                "saved": True,
                "travel_type_id": 2,
                "type_key": "ttf",
                "name": "골목을 가르는 여우",
                "description": (
                    "체력을 아낌없이 쓰는 활동형 여행자예요. 철저한 준비로 혼자만의 루트를 만들며 "
                    "도시의 문화와 에너지에서 영감을 받는 타입이에요. 그 지역의 이야기와 역사에 아낌없이 투자해요."
                ),
                "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/travel-types/ttf.png",
                "type_tags": ["액티비티형", "혼자형", "도시형"],
                "detail_cards": [
                    {"title": "몸으로 떠나는 여행", "description": "체력을 아낌없이 쓰는 게 진짜 여행이에요."},
                    {"title": "나만의 완벽한 루트", "description": "철저한 준비로 혼자만의 동선을 완성해요."},
                    {"title": "도시의 분위기", "description": "도시의 빛과 문화에서 영감을 받아요."},
                    {"title": "문화에 아낌없이", "description": "그 지역의 이야기와 역사에 아낌없이 투자해요."},
                ],
                "result_vector": [
                    {"label": "액티비티형", "value": 80},
                    {"label": "계획형", "value": 70},
                    {"label": "혼자형", "value": 60},
                    {"label": "자연형", "value": 30},
                    {"label": "문화형", "value": 70},
                    {"label": "가성비형", "value": 40},
                ],
                "accuracy": 40,
                "compatible_type": {
                    "travel_type_id": 1,
                    "type_key": "ttt",
                    "type_tags": ["액티비티형", "혼자형", "자연형"],
                    "name": "새벽을 달리는 늑대",
                    "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/travel-types/ttt.png",
                },
                "incompatible_type": {
                    "travel_type_id": 8,
                    "type_key": "fff",
                    "type_tags": ["힐링형", "단체형", "도시형"],
                    "name": "카페에 둥지 트는 참새",
                    "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/travel-types/fff.png",
                },
                "destinations": [
                    {
                        "place_id": 1,
                        "place_name": "부산 광안리 해수욕장",
                        "description": "광안대교의 야경이 펼쳐지는 해변",
                        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/places/img.jpg",
                        "tags": ["해수욕·해안", "카페·디저트"],
                        "style_vector": [
                            {"label": "액티비티형", "value": 80},
                            {"label": "계획형", "value": 60},
                            {"label": "혼자형", "value": 70},
                            {"label": "자연형", "value": 30},
                            {"label": "문화형", "value": 65},
                            {"label": "가성비형", "value": 40},
                        ],
                        "match_rate": 91,
                    },
                ],
            },
            response_only=True,
        ),
        OpenApiExample(
            "answers 길이 오류 응답",
            value={"error_detail": "answers 길이가 12여야 합니다."},
            response_only=True,
            status_codes=["400"],
        ),
    ],
    responses={
        200: QuizSubmitResponseSerializer,
        400: QuizErrorResponseSerializer,
    },
)

quiz_result_schema = extend_schema(
    tags=["User"],
    summary="내 퀴즈 결과 조회",
    description="로그인한 유저의 여행 성향 테스트 결과(마이페이지)를 조회합니다.",
    examples=[
        OpenApiExample(
            "퀴즈 결과 응답",
            value={
                "type_key": "ttf",
                "name": "골목을 가르는 여우",
                "description": (
                    "체력을 아낌없이 쓰는 활동형 여행자예요. 철저한 준비로 혼자만의 루트를 만들며 "
                    "도시의 문화와 에너지에서 영감을 받는 타입이에요. 그 지역의 이야기와 역사에 아낌없이 투자해요."
                ),
                "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/travel-types/ttf.png",
                "type_tags": ["액티비티형", "혼자형", "도시형"],
                "result_vector": [
                    {"label": "액티비티형", "value": 80},
                    {"label": "계획형", "value": 70},
                    {"label": "혼자형", "value": 60},
                    {"label": "자연형", "value": 30},
                    {"label": "문화형", "value": 70},
                    {"label": "가성비형", "value": 40},
                ],
                "accuracy": 40,
                "destinations": [
                    {"place_id": 1, "place_name": "부산 광안리 해수욕장", "match_rate": 91},
                    {"place_id": 2, "place_name": "전주 한옥마을", "match_rate": 85},
                    {"place_id": 3, "place_name": "강릉 안목해변", "match_rate": 78},
                ],
                "updated_at": "2026-05-22T12:23:11Z",
            },
            response_only=True,
        ),
        OpenApiExample(
            "인증 오류 응답",
            value={"error_detail": "자격 인증 데이터가 제공되지 않았습니다."},
            response_only=True,
            status_codes=["401"],
        ),
        OpenApiExample(
            "결과 없음 응답",
            value={"error_detail": "퀴즈 결과를 찾을 수 없습니다."},
            response_only=True,
            status_codes=["404"],
        ),
    ],
    responses={
        200: QuizResultSerializer,
        401: QuizErrorResponseSerializer,
        404: QuizErrorResponseSerializer,
    },
)

quiz_avatar_schema = extend_schema(
    tags=["TravelQuiz"],
    summary="퀴즈 결과 캐릭터를 프로필 이미지로 등록",
    description="travel_type_id로 지정한 여행 성향 캐릭터의 이미지를 로그인한 유저의 프로필 이미지로 등록합니다.",
    request=AvatarUpdateSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={"travel_type_id": 2},
            request_only=True,
        ),
        OpenApiExample(
            "등록 성공 응답",
            value={"updated": True},
            response_only=True,
        ),
        OpenApiExample(
            "잘못된 travel_type_id 응답",
            value={"error_detail": "유효하지 않은 travel_type_id입니다."},
            response_only=True,
            status_codes=["400"],
        ),
        OpenApiExample(
            "인증 오류 응답",
            value={"error_detail": "자격 인증 데이터가 제공되지 않았습니다."},
            response_only=True,
            status_codes=["401"],
        ),
    ],
    responses={
        200: AvatarUpdateResponseSerializer,
        400: QuizErrorResponseSerializer,
        401: QuizErrorResponseSerializer,
    },
)
