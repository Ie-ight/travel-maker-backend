"""여행 성향 유형(TravelType) 시드 데이터.

`seed_travel_types` 명령이 이 정의로 TravelType을 idempotent하게 upsert한다.
`description`은 DB에 저장하지 않고 응답 시점에 6축으로부터 동적으로 생성한다 (services.travel_quiz_services.make_description).
"""

TRAVEL_TYPE_SEEDS: dict[str, dict[str, str]] = {
    "ttt": {
        "name": "새벽을 달리는 늑대",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/ttt-wolf.webp",
    },
    "ttf": {
        "name": "골목을 가르는 여우",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/ttf-fox.webp",
    },
    "tft": {
        "name": "파도를 헤치는 기러기",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/tft-goose.webp",
    },
    "tff": {
        "name": "도시를 누비는 제비",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/tff-swallow.webp",
    },
    "ftt": {
        "name": "노을을 기다리는 사슴",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/ftt-deer.webp",
    },
    "ftf": {
        "name": "달빛 아래 걷는 고양이",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/ftf-cat.webp",
    },
    "fft": {
        "name": "강가에 모이는 백로",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/fft-heron.webp",
    },
    "fff": {
        "name": "카페에 둥지 트는 참새",
        "image_url": "https://travel-maker-bucket.s3.ap-northeast-2.amazonaws.com/avatar/fff-sparrow.webp",
    },
}
