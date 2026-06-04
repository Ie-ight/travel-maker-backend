# 장소 수집·태깅 커맨드 사용법

장소 데이터 수집부터 태그/성향 벡터 생성까지 쓰는 Django management command 정리 문서다.

## 공통 실행 방식

모든 `manage.py` 명령은 settings를 명시해야 한다.

아래 예시는 가독성을 위해 `python manage.py ... --settings=config.settings.local` 형태로 적는다. 실제 실행할 때는 환경에 맞게 Docker 컨테이너 안에서 실행하거나, 로컬 직접 실행 패턴으로 env를 로드한 뒤 실행한다.

Docker 컨테이너 안에서 실행:

```bash
docker compose -f infrastructure/docker/docker-compose.yml exec web \
  uv run python manage.py <command> --settings=config.settings.local
```

로컬에서 직접 실행:

```bash
set -a && . <(tr -d '\r' < envs/.env.local | grep -v '^#' | grep -v '^$') && set +a && \
DB_HOST=localhost uv run python manage.py <command> --settings=config.settings.local
```

필요한 주요 환경변수:

| 변수 | 쓰는 곳 | 의미 |
|---|---|---|
| `TOUR_API_CODE` | `sync_lcls_codes`, `sync_places` | 한국관광공사 Tour API 인증키 |
| `AI_TAGGING_PROVIDER` | `ai_tag` | 기본 AI provider. `gemini` 또는 `ollama` |
| `GEMINI_API_KEY` | `ai_tag --provider gemini` | Gemini API 키 |
| `GEMINI_MODEL` | `ai_tag --provider gemini` | Gemini 모델명. 기본값은 settings 참고 |
| `OLLAMA_HOST` | `ai_tag --provider ollama` | Ollama 서버 주소 |
| `OLLAMA_MODEL` | `ai_tag --provider ollama` | Ollama 모델명 |

## 권장 실행 순서

처음 DB를 채울 때는 아래 순서가 가장 안전하다.

```bash
# 1. 한국관광공사 분류 코드명 매핑 저장
python manage.py sync_lcls_codes --settings=config.settings.local

# 2. 태그 후보 시드 생성/갱신
python manage.py seed_tags --settings=config.settings.local

# 3. 장소 수집
python manage.py sync_places --content-type-id 14 --num-rows 10 --pages 1 --settings=config.settings.local

# 4. 기존 수집분에 지역·편의성 태그 재부여
python manage.py assign_tags --settings=config.settings.local

# 5. AI 태그 + 성향 벡터 생성
python manage.py ai_tag --limit 10 --only-missing --settings=config.settings.local
```

주의: `sync_places`는 장소 저장 후 `assign_deterministic_tags()`를 호출하므로 새로 수집되는 장소에는 지역·편의성 태그가 즉시 붙는다. `assign_tags`는 이미 수집된 기존 데이터에 태그를 다시 계산해서 붙일 때 사용한다.

## `sync_lcls_codes`

한국관광공사 `lclsSystmCode2` 분류 코드와 이름을 받아 `apps/place/services/lcls_codes.json`에 저장한다.

AI 태깅은 `VE/VE07/...` 같은 원시 코드 대신 사람이 읽을 수 있는 분류명으로 장소를 분석한다. 그래서 AI 태깅 전에 한 번 실행해두는 것이 좋다.

```bash
python manage.py sync_lcls_codes --settings=config.settings.local
```

실행 결과:

```text
분류 코드 N개 저장 -> lcls_codes.json
```

특징:

| 항목 | 동작 |
|---|---|
| 저장 대상 | `apps/place/services/lcls_codes.json` |
| 실패 처리 | 중간에 Tour API 오류가 나면 가능한 만큼 부분 저장 |
| 재실행 | 가능. 기존 JSON을 새 내용으로 다시 쓴다 |

## `seed_tags`

태그 후보를 DB의 `Tag` 테이블에 생성/갱신한다.

```bash
python manage.py seed_tags --settings=config.settings.local
```

생성되는 태그 타입:

| 태그 타입 | 부여 주체 | 예시 |
|---|---|---|
| `여행 스타일` | AI | `해변`, `문화`, `미식`, `액티비티` |
| `세부 테마` | AI | `박물관·전시`, `해수욕·해안`, `음식점` |
| `동행` | AI | `혼자`, `커플`, `가족`, `친구` |
| `지역` | 코드 규칙 | `서울`, `충남`, `제주` |
| `편의성` | 코드 규칙 | `주차`, `무료`, `반려동물` |

실행 결과:

```text
태그 시드 완료
  생성: X
  갱신: Y
  전체: Z
```

특징:

| 항목 | 동작 |
|---|---|
| 재실행 | 가능. `tag_name` 기준으로 있으면 갱신, 없으면 생성 |
| 필요한 시점 | `assign_tags`, `ai_tag` 실행 전 |
| 후보 소스 | `apps/place/services/tag_seeds.py`의 `TAG_SEEDS` |

## `sync_places`

한국관광공사 Tour API에서 장소를 수집한다. 목록, 상세 설명, 이미지, 운영정보를 가져오고 저장 후 지역·편의성 태그까지 붙인다.

### 소량 검증 모드

기본 모드다. 특정 관광 타입을 지정해서 몇 페이지까지만 수집한다.

```bash
python manage.py sync_places \
  --content-type-id 14 \
  --num-rows 10 \
  --pages 1 \
  --settings=config.settings.local
```

위 명령의 의미:

| 옵션 | 값 | 의미 |
|---|---:|---|
| `--content-type-id` | `14` | 문화시설만 수집 |
| `--num-rows` | `10` | 페이지당 10개 조회 |
| `--pages` | `1` | 1페이지만 조회 |

관광 타입 주요 값:

| ID | 타입 |
|---:|---|
| `12` | 관광지 |
| `14` | 문화시설 |
| `15` | 축제공연행사 |
| `28` | 레포츠 |
| `32` | 숙박 |
| `38` | 쇼핑 |
| `39` | 음식점 |

지역 필터를 걸고 싶으면 `--ldong-regn-cd`를 추가한다.

```bash
python manage.py sync_places \
  --content-type-id 39 \
  --ldong-regn-cd 11 \
  --num-rows 100 \
  --pages 2 \
  --settings=config.settings.local
```

위 명령은 서울(`11`) 음식점 2페이지를 수집한다.

### 대량 적재 모드: `--all`

전체 기본 타입을 전국 기준으로 끝까지 수집한다.

```bash
python manage.py sync_places --all --settings=config.settings.local
```

`--all`의 기본 타입:

```text
12, 14, 15, 28, 32, 38, 39
```

`--all`에서는 기본 `num_rows`가 1000이다. 이미 저장된 `content_id`는 기본으로 건너뛴다.

```bash
python manage.py sync_places \
  --all \
  --max-pages 3 \
  --settings=config.settings.local
```

위 명령은 타입별 최대 3페이지만 수집한다. 대량 수집 전 테스트에 쓸 수 있다.

```bash
python manage.py sync_places \
  --all \
  --refresh \
  --settings=config.settings.local
```

위 명령은 이미 저장된 장소도 다시 상세 조회해서 갱신한다. API 호출량이 커지므로 필요한 경우에만 사용한다.

### 증분 동기화 모드: `--sync`

`areaBasedSyncList2`를 사용해 신규·변경·삭제 신호를 반영한다.

```bash
python manage.py sync_places --sync --settings=config.settings.local
```

동작:

| 상황 | 처리 |
|---|---|
| 신규 `content_id` | 상세 조회 후 새 장소 저장 |
| 기존 장소이고 `modifiedtime`이 더 큼 | 상세 재조회 후 갱신 |
| 기존 장소이고 `modifiedtime` 변화 없음 | 상세 호출 없이 스킵 |
| `showflag=0` | `is_active=False`로 소프트삭제 |

제한 테스트:

```bash
python manage.py sync_places \
  --sync \
  --max-pages 2 \
  --dry-run \
  --settings=config.settings.local
```

위 명령은 타입별 최대 2페이지만 증분 목록을 확인하고 DB 저장은 하지 않는다.

### `sync_places` 옵션 정리

| 옵션 | 기본값 | 적용 모드 | 효과 |
|---|---:|---|---|
| `--content-type-id` | `14` | 소량 | 특정 관광 타입만 수집 |
| `--ldong-regn-cd` | 없음 | 소량 | 법정동 시도 코드로 지역 필터 |
| `--num-rows` | 소량 `10`, `--all/--sync` `1000` | 전체 | 페이지당 조회 개수 |
| `--pages` | `1` | 소량 | 조회할 페이지 수 |
| `--all` | 꺼짐 | 대량 | 기본 타입 전체를 끝까지 수집 |
| `--sync` | 꺼짐 | 증분 | 변경분만 반영 |
| `--max-pages` | 없음 | `--all/--sync` | 타입별 최대 페이지 수 제한 |
| `--refresh` | 꺼짐 | `--all` | 기존 장소도 다시 상세 조회 |
| `--dry-run` | 꺼짐 | 전체 | 목록만 조회하고 DB 저장 안 함 |

`--all`과 `--sync`는 같이 사용할 수 없다.

실행 결과 카운터:

| 항목 | 의미 |
|---|---|
| `조회` | 목록에서 확인한 항목 수 |
| `이미지 없어 스킵` | `firstimage`가 없어 저장하지 않은 항목 수 |
| `기존이라 스킵` | `--all` 기본 재개 모드에서 이미 있던 장소 수 |
| `미변경 스킵` | `--sync`에서 `modifiedtime` 변화가 없어 넘긴 장소 수 |
| `생성` | 새로 만든 장소 수 |
| `갱신` | 기존 장소를 업데이트한 수 |
| `비활성화(삭제)` | `showflag=0`으로 `is_active=False` 처리한 수 |
| `이미지 저장` | 저장한 이미지 수 |
| `운영정보 저장` | `PlaceInfo`를 저장/갱신한 수 |

## `assign_tags`

이미 수집된 장소에 지역·편의성 태그를 다시 계산해서 붙인다.

```bash
python manage.py assign_tags --settings=config.settings.local
```

특정 타입만 처리:

```bash
python manage.py assign_tags \
  --content-type-id 39 \
  --settings=config.settings.local
```

위 명령은 음식점 타입만 지역·편의성 태그를 재계산한다.

동작:

| 태그 타입 | 기준 |
|---|---|
| `지역` | `address_primary` 첫 토큰. 예: `충청남도 ...` -> `충남` |
| `편의성` | `PlaceInfo.parking`, `pet`, `baby_carriage`, `credit_card`, `admission_fee` |

중요한 특징:

| 항목 | 동작 |
|---|---|
| 기존 지역·편의성 태그 | 먼저 제거 후 다시 계산 |
| 기존 AI 태그 | 건드리지 않음 |
| 재실행 | 가능. 여러 번 실행해도 최종 결과가 중복되지 않음 |
| 선행 조건 | `seed_tags`가 먼저 실행되어 있어야 실제 태그가 붙음 |

## `ai_tag`

수집된 장소에 AI 태그와 6차원 `style_vector`를 생성한다.

AI가 부여하는 태그 타입:

```text
여행 스타일, 세부 테마, 동행
```

성향 벡터 순서:

```text
[활동성, 계획성, 사교성, 공간지향, 경험지향, 소비스타일]
```

기본 실행:

```bash
python manage.py ai_tag --settings=config.settings.local
```

기본 동작:

| 항목 | 기본값 |
|---|---|
| 처리 대상 | `is_active=True`이고 `description`이 있는 장소 |
| 처리 개수 | `--limit 10` |
| provider | `AI_TAGGING_PROVIDER` 설정값 |
| DB 저장 | 저장함 |

### 먼저 결과만 확인: `--dry-run`

```bash
python manage.py ai_tag \
  --limit 3 \
  --dry-run \
  --provider ollama \
  --settings=config.settings.local
```

위 명령은 장소 3개를 AI 분석하지만 DB에는 저장하지 않는다.

### 아직 벡터 없는 장소만 처리: `--only-missing`

```bash
python manage.py ai_tag \
  --only-missing \
  --limit 100 \
  --provider ollama \
  --settings=config.settings.local
```

위 명령은 `PlaceFeature`가 없는 장소 100개만 처리한다. 중간에 끊긴 AI 태깅을 이어갈 때 사용한다.

### 특정 관광 타입만 처리

```bash
python manage.py ai_tag \
  --content-type-id 14 \
  --limit 50 \
  --provider ollama \
  --settings=config.settings.local
```

위 명령은 문화시설 50개만 AI 태깅한다.

### Gemini로 처리

```bash
python manage.py ai_tag \
  --provider gemini \
  --limit 20 \
  --only-missing \
  --rpm 4 \
  --settings=config.settings.local
```

위 명령은 Gemini로 미태깅 장소 20개를 처리하고, 분당 최대 4회 요청으로 제한한다.

주의:

| 항목 | 설명 |
|---|---|
| `GEMINI_API_KEY` | 설정되어 있지 않으면 명령이 실패한다 |
| 비용/한도 | 원격 API이므로 `--limit`, `--rpm`, `--only-missing`을 같이 쓰는 것이 안전하다 |

### Ollama로 처리

```bash
python manage.py ai_tag \
  --provider ollama \
  --model gemma3:12b \
  --only-missing \
  --limit 500 \
  --settings=config.settings.local
```

위 명령은 로컬 Ollama의 `gemma3:12b` 모델로 미태깅 장소 500개를 처리한다.

주의:

| 항목 | 설명 |
|---|---|
| Ollama 서버 | `OLLAMA_HOST`에서 접근 가능해야 한다 |
| Docker에서 호스트 Ollama 접근 | 기본 설정은 `http://host.docker.internal:11434` |
| 기본 RPM | Ollama는 기본 무제한 |

### Markdown 결과 파일 저장: `--out`

```bash
python manage.py ai_tag \
  --limit 10 \
  --dry-run \
  --provider ollama \
  --out reports/ai_tags.md \
  --settings=config.settings.local
```

위 명령은 결과를 `reports/ai_tags.md`에 표로 저장한다. `--dry-run`과 같이 쓰면 DB 저장 없이 검토용 표만 만들 수 있다.

저장되는 표 컬럼:

```text
id, 장소, 타입, 분류, 여행 스타일, 세부 테마, 동행, 벡터, 근거
```

### 골든 샘플만 처리: `--golden`

```bash
python manage.py ai_tag \
  --golden \
  --dry-run \
  --provider ollama \
  --out reports/golden_ai_tags.md \
  --settings=config.settings.local
```

위 명령은 `apps/place/services/golden_sample.json`에 있는 `content_id` 목록만 처리한다.

특징:

| 항목 | 동작 |
|---|---|
| 대상 | 골든 샘플 `content_id`에 해당하는 장소 |
| 무시되는 옵션 | `--content-type-id`, `--only-missing`, `--limit` |
| 용도 | 프롬프트 수정 후 결과가 좋아졌는지 회귀 확인 |

### `ai_tag` 옵션 정리

| 옵션 | 기본값 | 효과 |
|---|---:|---|
| `--content-type-id` | 없음 | 특정 관광 타입만 처리 |
| `--limit` | `10` | 처리할 최대 장소 수 |
| `--only-missing` | 꺼짐 | `PlaceFeature`가 없는 장소만 처리 |
| `--dry-run` | 꺼짐 | 분석만 하고 DB 저장 안 함 |
| `--provider` | settings 기본값 | `gemini` 또는 `ollama` 선택 |
| `--model` | provider 기본값 | 사용할 모델명 직접 지정 |
| `--out` | 없음 | Markdown 결과 파일 저장 |
| `--golden` | 꺼짐 | 골든 샘플만 처리 |
| `--rpm` | Gemini `8`, Ollama `0` | 분당 요청 수 제한. `0`은 무제한 |

실행 결과 카운터:

| 항목 | 의미 |
|---|---|
| `처리` | AI 분석 결과를 얻은 장소 수. `--dry-run`이면 저장은 안 함 |
| `보류(overview 없음)` | 분석 결과가 없어 넘어간 수 |
| `실패` | AI 호출, JSON 파싱, 벡터 검증 등에 실패한 수 |

## 자주 쓰는 조합

### 처음 10개만 수집부터 AI 태깅까지 확인

```bash
python manage.py sync_lcls_codes --settings=config.settings.local
python manage.py seed_tags --settings=config.settings.local
python manage.py sync_places --content-type-id 14 --num-rows 10 --pages 1 --settings=config.settings.local
python manage.py ai_tag --content-type-id 14 --limit 10 --dry-run --provider ollama --settings=config.settings.local
```

결과가 괜찮으면 마지막 명령에서 `--dry-run`을 빼고 저장한다.

### 대량 수집 재개

```bash
python manage.py sync_places --all --settings=config.settings.local
```

`--all`은 기본적으로 기존 장소를 스킵하므로 중간에 끊겨도 다시 실행하기 좋다.

### 로컬 Ollama로 전량 AI 태깅 이어가기

```bash
python manage.py ai_tag \
  --provider ollama \
  --only-missing \
  --limit 1000 \
  --out reports/ai_tags_batch.md \
  --settings=config.settings.local
```

### 운영 환경에서 Gemini로 하루 제한량만 처리

```bash
python manage.py ai_tag \
  --provider gemini \
  --only-missing \
  --limit 20 \
  --rpm 4 \
  --settings=config.settings.local
```

### 월 1회 증분 수집 후 미태깅분만 채우기

```bash
python manage.py sync_places --sync --settings=config.settings.local
python manage.py ai_tag --provider gemini --only-missing --limit 20 --settings=config.settings.local
```

증분 수집은 신규/변경 장소를 저장하면서 지역·편의성 태그를 붙인다. AI 태그와 벡터는 `ai_tag`가 별도로 채운다.
