# 단계 7 — 정기 증분 동기화 + API/태깅 운영 (설계)

단계 6(초기 대량 적재)에 이어, 운영 중 **변경분을 싸게 반영**하고 **API·AI 호출을 아끼는** 메커니즘.
구현은 단계 6의 `sync_all`·`_process_list_item`·`TourApiClient` 재시도를 재사용한다. (본 문서는 설계, 코드는 후속.)

## 배경 / 제약

운영하면 데이터가 ① 새로 생기고 ② 바뀌고 ③ 사라진다. 매 주기 전량 재조회는 ~49,700곳 × 상세 3콜 ≈
**15만 콜** 낭비. 또한 **배포 환경엔 ollama가 없다(로컬 전용)** → prod의 AI 태깅은 **Gemini(무료 20콜/일)만** 가능.

## 1. 증분 동기화 — `areaBasedSyncList2` (실측 반영)

블라인드 전량 대신 변경분만. **실측 확인**:
- 응답이 `areaBasedList2`의 모든 필드 + **`showflag`** + **`modifiedtime`**(`20251111151027`, YYYYMMDDHHMMSS).
- type14 totalCount가 **3090**(areaBasedList는 2657) → **`showflag=0`(비공개/삭제) 항목까지 포함** = 삭제 신호.
- **서버측 날짜 필터는 안 됨**(`modifiedtime=20250101` → 0건). → 목록은 **전량 스캔**(타입당 ~수 페이지@1000건, 전체 ~50콜로 저렴)하고 **`modifiedtime` 필드를 클라이언트에서 비교**.

**설계**:
- `Place`에 `source_modified_at`(목록 `modifiedtime`) 저장 → **per-place 비교**가 상태이므로 **별도 커서 테이블 불필요**.
  > §4 "modifiedtime 저장 안 함"을 단계 7에서 개정(증분 핵심 신호).
- **주기**: Celery Beat **월 1회**(권장 — 변경 빈도 낮음. 목록 스캔이 싸 주 1회도 부담 없음).
- **처리(델타 content_id별)**:
  - `showflag=0` → **소프트삭제**(`is_active=False`. 리뷰·북마크 FK 보존, 복구 가능).
  - 신규 content_id → `_process_list_item`로 수집.
  - 기존 & 목록 `modifiedtime` > 저장 `source_modified_at` → detail 재조회·`update_or_create` 갱신.
  - 기존 & 미변경 → **스킵(detail 0콜)** — negative caching 자동.

## 2. 상세 없는 곳 재조회 절약 (확정)

`modifiedtime` 비교로 **미변경 곳은 detail 재호출 0콜**. 30일 TTL은 "변했을까?"의 시간 추정이라 변경을 놓치거나
헛조회가 남는다 → 불필요. 단 **전송 실패로 빈 것**(≠데이터 없음)은 재시도 대상이라 영구 스킵하지 말고 짧게(1일) 미뤘다 재시도(선택 backstop).

## 3. 전량 재조회 주기 (확정)

블라인드 2년 전량(~15만 콜)은 비권장. 증분(1)이 상시 최신을 유지. **연 1회 "가벼운 감사"**(목록만으로 타입별
`totalCount`·누락 content_id 비교, ~50콜)로 증분이 놓친 게 없는지 점검 → 누락분만 보충. 전량 detail 재호출은 거의 불필요.

## 4. AI 태깅 운영 — 배포는 Gemini만 ★핵심

**제약**: prod엔 ollama 없음 → Gemini(20콜/일)만. 산수:
- ~40k곳을 Gemini 20/일 = **~5.5년(불가)**. ollama 로컬 = ~6일 연속(가능).

**전략 — 초기는 로컬 ollama, 운영은 Gemini 증분**:
- **초기 대량(1회)**: 로컬(개발 맥)에서 `ai_tag`(ollama, gemma3:12b)로 전량 태깅 → `PlaceFeature` 벡터 포함 DB를
  prod에 적재(`pg_dump`/로드). 50k 벡터는 이전 산정상 ~14MB(gzip)라 이전 부담 작음.
- **운영(증분)**: 수집(step 7)·결정론 태그(지역·편의성)는 ollama 불필요 → prod에서 바로 동작. **AI 벡터/태그만**
  Gemini로. Beat **일 1회** `ai_tag --provider gemini --limit 20 --only-missing` → 미태깅 백로그를 20/일로 소진.
  - 신규 장소는 수집·결정론 태그가 즉시 붙고, AI 벡터는 ~1일 내 채워짐(허용).
  - 월 증분(수십~수백)이 평균 20/일 미만이면 따라잡음. 스파이크는 `--only-missing`이라 다음날 이어서 소진.
- **일일 캡 구현**: `--limit 20` + 일 1회 스케줄(MVP). 중복 실행으로 한도 초과를 막으려면 provider별 **DB 일일
  카운터**(`(date, provider) → count`)가 견고 — 선택. (`--rpm` 분당 제한은 이미 있음.)
- 지속적으로 증분 > 캡이면 **Gemini 유료 등급** 검토.

## 운영 루프

```
[월 1회 Beat]  areaBasedSyncList2 델타 → showflag=0 소프트삭제 / 신규·변경 detail → 결정론 태그
[일 1회 Beat]  ai_tag --provider gemini --limit 20 --only-missing  (AI 태깅 백로그 20/일 소진)
[연 1회]       목록 기반 가벼운 감사(totalCount·누락 점검)
[배포 전 1회]  로컬 ollama로 전량 AI 태깅 → 벡터 포함 DB 적재
```

## 남은 결정 / 구현 작업

1. 마이그레이션: `Place.source_modified_at`(증분), `Place.is_active`(소프트삭제).
2. `areaBasedSyncList2` 페이지네이션 끝까지 + `showflag=0` 표본 실측(구현 시).
3. 증분 주기 월 1회 확정(또는 주 1회).
4. Gemini 캡: `--limit` 방식(MVP) vs DB 일일 카운터(견고) — 운영 안정성 보고 선택.
5. `sync_incremental` 서비스 + Beat 스케줄 + 관리 명령(`sync_places --sync` 등) 추가.

## 재사용 (단계 6 자산)

- `sync_all`/`_process_list_item`: 델타 content_id 처리에 재사용.
- `TourApiClient` 재시도·백오프·resultCode: 증분 호출에 그대로.
- `skip_existing` → `source_modified_at` 비교로 일반화.
