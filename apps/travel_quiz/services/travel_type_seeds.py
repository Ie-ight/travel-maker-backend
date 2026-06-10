"""여행 성향 유형(TravelType) 시드 데이터.

`seed_travel_types` 명령이 이 정의로 TravelType을 idempotent하게 upsert한다.
`description`은 DB에 저장하지 않고 응답 시점에 6축으로부터 동적으로 생성한다 (services.travel_quiz_services.make_description).

`image_url`은 아직 S3 URL을 받지 못해 빈 문자열로 시딩한다 — 추후 실제 URL 확보 시
이 딕셔너리를 갱신하고 동일 명령을 재실행하면 된다.
"""

TRAVEL_TYPE_SEEDS: dict[str, dict[str, str]] = {
    "ttt": {
        "name": "새벽을 달리는 늑대",
        "image_url": "",
    },
    "ttf": {
        "name": "골목을 가르는 여우",
        "image_url": "",
    },
    "tft": {
        "name": "파도를 헤치는 기러기",
        "image_url": "",
    },
    "tff": {
        "name": "도시를 누비는 제비",
        "image_url": "",
    },
    "ftt": {
        "name": "노을을 기다리는 사슴",
        "image_url": "",
    },
    "ftf": {
        "name": "달빛 아래 걷는 고양이",
        "image_url": "",
    },
    "fft": {
        "name": "강가에 모이는 백로",
        "image_url": "",
    },
    "fff": {
        "name": "카페에 둥지 트는 참새",
        "image_url": "",
    },
}
