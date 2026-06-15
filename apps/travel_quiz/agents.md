# Travel Quiz App — Agent Guidance

Scoped guidance for `apps/travel_quiz/`. Follow the project-level `AGENTS.md` for all general rules.

---

## Overview

Handles travel personality test. Receives 12 A/B answers, calculates 6-axis scores, determines one of 8 travel types, and returns results with recommended places. Login users' results are auto-saved inside `submit`; guest users get results only (no persistence).

---

## Models

### TravelType
- 8 fixed types: `ttt`, `ttf`, `tft`, `tff`, `ftt`, `ftf`, `fft`, `fff`
  - `type_key` order: `activity + social + space` (e.g. `"ftf"` = healing + solo + city)
  - Initial data loaded via seed — never create in code
  - `image_url`: S3 URL, managed via seed data
  - `description`: NOT stored in DB — dynamically generated from all 6 axes at response time

### UserTestResult
- `OneToOneField(user)` — one result per user only
  - Always use `update_or_create` — never `create()` directly
  - `result_vector`: `VectorField(dimensions=6)` via pgvector
    - Order: `[activity, plan, social, space, experience, budget]`
    - Range: `0.0 ~ 1.0`, normalized by `(score + 5) / 10`

---

## Business Rules

### Score Calculation
- Receive 12 answers (`"A"` or `"B"`), accumulate weights per choice
  - Weight data managed as code constants (`QUIZ_DATA`) — no DB query
  - Normalize each axis: `norm = max(0.0, min(1.0, (score + 5) / 10))`

### Type Determination
- Use only 3 axes in order: `activity → social → space`
  - `>= 0.5` → `t`, `< 0.5` → `f`
  - `type_key = activity + social + space` (e.g. `"ftf"`)
  - Remaining 3 axes (plan, experience, budget) included in `result_vector` but not used for type determination

### Recommended Places
- Calculate cosine similarity between user `result_vector` and `Place.style_vector`
  - Return top 3 closest places
  - Use pgvector operator: `Place.objects.order_by(CosineDistance('style_vector', result_vector))[:3]`

### Auto Save (inside submit)
- If `request.user.is_authenticated` → save result via `update_or_create`
  - If guest → skip save, return `saved: false`
  - No separate save endpoint — handled entirely inside `submit` view

---

## API Endpoints

| Method | URL | Auth | Notes |
|---|---|---|---|
| POST | `/api/v1/quiz/submit` | ❌ | Submit answers; auto-saves for login users; returns `saved` flag |
| GET | `/api/v1/users/quiz/result` | ✅ | Mypage result (name / description / image_url / type_tags) |
| PATCH | `/api/v1/users/avatar` | ✅ | travel_type_id → TravelType.image_url → update user profile image |

---

## Validation

- `answers` length must be exactly 12
  - Each element must be `"A"` or `"B"` only
  - Violation → `400 Bad Request`
  - Non-existent `travel_type_id` → `400 Bad Request`

---

## Do Not

- Do not query `QUIZ_DATA` from DB — manage as code constants
  - Do not use `UserTestResult.objects.create()` — use `update_or_create`
  - Do not write type determination logic in views — handle in service layer
  - Do not implement a separate save endpoint — save is handled inside `submit`
  - Do not implement S3 upload logic in this app — image URLs are managed via seed data

---

## Quiz Data & Calculation Logic

### Weight Data (QUIZ_DATA)
12 questions, each choice has weights for 6 axes in order:
`[activity, plan, social, space, experience, budget]`

```python
QUIZ_DATA = [
    {
        "a": {"label": "글램핑·독채", "weights": [ 0, 0, 1, 1, 0, 1]},
        "b": {"label": "시티 호텔",   "weights": [ 0, 0,-1,-1, 0,-1]},
    },
    {
        "a": {"label": "항목별 예산표", "weights": [ 0, 1, 0, 0, 0, 1]},
        "b": {"label": "그냥 카드 긁기","weights": [ 0,-1, 0, 0, 0,-1]},
    },
    {
        "a": {"label": "일찍 루트대로 출발", "weights": [ 1, 1, 0, 0, 0, 0]},
        "b": {"label": "알람 없이 뒹굴",     "weights": [-1,-1, 0, 0, 0, 0]},
    },
    {
        "a": {"label": "자연·트레킹 코스", "weights": [ 0, 1, 0, 1, 0, 0]},
        "b": {"label": "도심 핫플 투어",   "weights": [ 0,-1, 0,-1, 0, 0]},
    },
    {
        "a": {"label": "바로 첫 스팟 출발",    "weights": [ 1, 1, 1, 0, 0, 0]},
        "b": {"label": "카페에서 계획 세우기", "weights": [-1,-1,-1, 0, 0, 0]},
    },
    {
        "a": {"label": "혼자 골목 산책",  "weights": [-1, 0, 1, 0, 0, 0]},
        "b": {"label": "다같이 액티비티", "weights": [ 1, 0,-1, 0, 0, 0]},
    },
    {
        "a": {"label": "서핑·트레킹", "weights": [ 1, 0, 0, 1,-1, 0]},
        "b": {"label": "미술관·공연", "weights": [-1, 0, 0,-1, 1, 0]},
    },
    {
        "a": {"label": "혼자 조용히", "weights": [ 0, 0, 1, 0, 1, 0]},
        "b": {"label": "다같이 우르르","weights": [ 0, 0,-1, 0,-1, 0]},
    },
    {
        "a": {"label": "국립공원 트레킹",  "weights": [ 0, 0, 0, 1,-1, 1]},
        "b": {"label": "갤러리·파인다이닝","weights": [ 0, 0, 0,-1, 1,-1]},
    },
    {
        "a": {"label": "로컬 축제·시장", "weights": [ 1, 0, 0, 0, 1, 1]},
        "b": {"label": "럭셔리 풀빌라",  "weights": [-1, 0, 0, 0,-1,-1]},
    },
    {
        "a": {"label": "미리 공부하고 감상", "weights": [ 0, 1, 0, 0, 1, 0]},
        "b": {"label": "그냥 가서 느끼기",   "weights": [ 0,-1, 0, 0,-1, 0]},
    },
    {
        "a": {"label": "혼자 해변 노을",   "weights": [ 0, 0, 1, 1, 0, 1]},
        "b": {"label": "루프탑 바 칵테일", "weights": [ 0, 0,-1,-1, 0,-1]},
    },
]
```

### Normalization
```python
scores = [0] * 6
for answer, question in zip(answers, QUIZ_DATA):
    weights = question[answer.lower()]["weights"]
    for i, w in enumerate(weights):
        scores[i] += w

norm = [max(0.0, min(1.0, (s + 5) / 10)) for s in scores]
# result_vector = norm  →  [activity, plan, social, space, experience, budget]
```

### Type Key Determination
```python
is_active = norm[0] >= 0.5  # activity
is_solo   = norm[2] >= 0.5  # social (t = solo, f = group)
is_nature = norm[3] >= 0.5  # space  (t = nature, f = city)

type_key = ("t" if is_active else "f") + \
           ("t" if is_solo   else "f") + \
           ("t" if is_nature else "f")
```

### Dynamic Description (make_desc)
Generated from all 6 axes — not stored in DB. Response field name: `description`
```python
is_planned  = norm[1] >= 0.5  # plan   (t = planned, f = spontaneous)
is_cultural = norm[4] >= 0.5  # experience (t = cultural, f = activity)
is_budget   = norm[5] >= 0.5  # budget (t = budget-friendly, f = luxury)

# d1: activity axis
# t → "체력을 아낌없이 쓰는 활동형 여행자예요."
# f → "천천히 스며드는 여행을 좋아하는 힐링형 여행자예요."

# d2: (is_planned, is_solo) combination
# (True,  True)  → "철저한 준비로 혼자만의 루트를 만들며"
# (False, True)  → "계획 없이도 혼자 유연하게 움직이는 걸 즐기며"
# (True,  False) → "철저한 준비로 일행 모두의 동선을 짜며"
# (False, False) → "즉흥적인 선택으로 함께하는 우연을 사랑하며"

# d3: space axis
# t → "자연 속에서 에너지를 충전하는 타입이에요."
# f → "도시의 문화와 에너지에서 영감을 받는 타입이에요."

# d4: (is_cultural, is_budget) combination
# (True,  True)  → "현지 문화를 가성비 있게 깊이 파고드는 걸 즐겨요."
# (True,  False) → "그 지역의 이야기와 역사에 아낌없이 투자해요."
# (False, True)  → "직접 체험하는 여행을 합리적인 가격에 즐겨요."
# (False, False) → "특별한 체험을 위해서라면 지갑 열기를 주저 않아요."

# final: f"{d1} {d2} {d3} {d4}"
```

## Architecture

- Views handle response only — validation, calculation, save, and recommendation logic must go in service layer
  - Always set explicit HTTP status codes in views (e.g. `status=status.HTTP_200_OK`)

## Tag Reference

`TravelType.type_tags` are personality axis tags — not from TAG_SEEDS.
These are fixed per type_key and do not reference Tag model.

| type_key | type_tags |
|---|---|
| ttt | 액티비티형, 혼자형, 자연형 |
| ttf | 액티비티형, 혼자형, 도시형 |
| tft | 액티비티형, 단체형, 자연형 |
| tff | 액티비티형, 단체형, 도시형 |
| ftt | 힐링형, 혼자형, 자연형 |
| ftf | 힐링형, 혼자형, 도시형 |
| fft | 힐링형, 단체형, 자연형 |
| fff | 힐링형, 단체형, 도시형 |

Note: `destinations[].tags` are 1차 태그 from Tag model (`tag_type="여행 스타일"`).
Do not confuse `type_tags` with place tags.

## Travel Type Seed Data

8 fixed types — used for `seed_travel_types` management command.
Run after `seed_tags` completes.
`image_url` must be filled before seeding (S3 URL).
`description` is NOT stored in DB — dynamically generated from all 6 axes at response time.

```python
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
```

Note: `type_tags` are not stored in DB — generated from type_key at response time.

## detail_cards

4 fixed-order cards — dynamically generated from axis results, not stored in DB.
Included in `submit` response only.

### card 1 — activity axis
| condition | title | description |
|---|---|---|
| activity ≥ 0.5 | 몸으로 떠나는 여행 | 체력을 아낌없이 쓰는 게 진짜 여행이에요. |
| activity < 0.5 | 천천히 스며드는 여행 | 여유롭게 흡수하는 것이 나만의 여행법이에요. |

### card 2 — plan × social axes
| condition | title | description                 |
|---|---|-----------------------------|
| plan ≥ 0.5 + social ≥ 0.5 (planned + solo) | 나만의 완벽한 루트 | 철저한 준비로 혼자만의 동선을 완성해요.      |
| plan < 0.5 + social ≥ 0.5 (spontaneous + solo) | 즉흥적인 이동 | 계획 없이 끌리는 골목으로 자유롭게 떠나요.    |
| plan ≥ 0.5 + social < 0.5 (planned + group) | 완벽한 단체 동선 | 철저한 준비로 일행 모두의 여행을 완성해요.    |
| plan < 0.5 + social < 0.5 (spontaneous + group) | 함께하는 우연 | 즉흥적인 선택으로 함께 만드는 특별한 순간이에요. |

### card 3 — space axis
| condition | title | description |
|---|---|---|
| space ≥ 0.5 (nature) | 자연 속 충전 | 자연 속에서 에너지를 회복하는 타입이에요. |
| space < 0.5 (city) | 도시의 분위기 | 도시의 빛과 문화에서 영감을 받아요. |

### card 4 — experience × budget axes
| condition | title | description |
|---|---|---|
| experience ≥ 0.5 + budget ≥ 0.5 (cultural + budget-friendly) | 알뜰한 문화 탐방 | 현지 문화를 가성비 있게 깊이 파고들어요. |
| experience ≥ 0.5 + budget < 0.5 (cultural + luxury) | 문화에 아낌없이 | 그 지역의 이야기와 역사에 아낌없이 투자해요. |
| experience < 0.5 + budget ≥ 0.5 (activity + budget-friendly) | 합리적인 체험 | 직접 체험하는 여행을 합리적인 가격에 즐겨요. |
| experience < 0.5 + budget < 0.5 (activity + luxury) | 특별한 경험엔 아낌없이 | 기억에 남을 순간엔 지갑을 열어요. |
