# place 데이터 덤프 복원 가이드 (동료용)

한국관광공사 Tour API로 대량 수집 + AI 태깅한 `place` 도메인 데이터 덤프입니다.
재수집(키 한도·수십 시간) 없이 이 덤프로 바로 같은 데이터를 받을 수 있어요.

## 포함 테이블 (6개)

| 테이블 | 내용 |
|---|---|
| `places` | 장소 본문(이름·좌표·주소·설명·홈페이지·분류 등) |
| `place_placeimage` | 장소 이미지(대표/갤러리) |
| `place_info` | 운영정보(운영시간·휴무·주차·요금 등) |
| `place_tag` | 태그 사전(지역·편의성·여행스타일·세부테마·동행) |
| `places_tags` | 장소↔태그 연결(M2M) |
| `place_features` | AI 산출 `style_vector`(6축, **pgvector**) |

> 6개 테이블은 외부 FK가 없어 단독 복원됩니다. 단 `place_features.style_vector`가 **pgvector** 타입이라 대상 DB에 확장이 있어야 해요.

## 사전 준비

1. 프로젝트 클론 + 마이그레이션으로 **스키마 생성** (pgvector 확장 포함, 마이그레이션 0004):
   ```bash
   python manage.py migrate --settings=config.settings.local
   ```
2. (Docker 사용 시) db 컨테이너로 덤프 파일 복사:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.yml cp place_dump_*.dump db:/tmp/
   ```

## 복원 (데이터만 적재 — 권장)

스키마는 이미 migrate로 만들어졌으므로 **데이터만** 넣습니다.
기존에 place 데이터가 있다면 PK 충돌이 나니, **빈 상태**에서 하거나 아래 6개 테이블을 먼저 비우세요(TRUNCATE).

```bash
# Docker db 컨테이너 안에서 실행하는 예
pg_restore --data-only --no-owner --disable-triggers \
  -U travel_maker_user -d travel_maker_db /tmp/place_dump_*.dump
```

- `--disable-triggers`: FK 검증 순서 문제 회피(슈퍼유저 권한 필요).
- 충돌 시: `psql -c 'TRUNCATE places, place_placeimage, place_info, place_tag, place_features, places_tags RESTART IDENTITY CASCADE;'` 후 재시도.

## 복원 (스키마째 통째로 교체)

빈 DB에 스키마+데이터를 한 번에:

```bash
pg_restore --clean --if-exists --no-owner \
  -U travel_maker_user -d travel_maker_db /tmp/place_dump_*.dump
```

## 확인

```bash
python manage.py shell -c "from apps.place.models import Place, PlaceFeature; print('장소', Place.objects.count(), '/ 태깅', PlaceFeature.objects.count())"
```
