#!/usr/bin/env bash
# place 도메인 데이터 pg_dump (동료 공유용).
#
# 한국관광공사 Tour API로 대량 수집·AI 태깅한 place 데이터를 동료들이 재수집 없이 받을 수 있도록
# place 관련 6개 테이블만 커스텀 포맷(-Fc)으로 떠서 호스트 dumps/ 에 저장한다.
#   places / place_placeimage / place_info / place_tag / place_features / places_tags
# (이 6개는 외부 FK가 없어 단독 복원 가능. place_features.style_vector는 pgvector 타입.)
#
# 복원(동료): dumps/RESTORE.md 참고. 요지 ─ 대상 DB에 pgvector 확장 필요(마이그레이션 0004),
#   스키마는 migrate로 만든 뒤 데이터만 적재 권장:
#     pg_restore --data-only --no-owner -d <DB> place_dump_*.dump
set -euo pipefail

cd "$(dirname "$0")/../.."  # 프로젝트 루트로 이동
COMPOSE="docker compose -f infrastructure/docker/docker-compose.yml"
DB_USER="travel_maker_user"
DB_NAME="travel_maker_db"
TABLES="-t places -t place_placeimage -t place_info -t place_tag -t place_features -t places_tags"

TS="$(date +%Y%m%d_%H%M)"
FILE="place_dump_${TS}.dump"

mkdir -p dumps
echo "▶ pg_dump 실행 (db 컨테이너, 커스텀 포맷)…"
# --no-owner/--no-privileges: 동료 DB에 동일 role이 없어도 복원되게.
$COMPOSE exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-privileges $TABLES -f "/tmp/${FILE}"
$COMPOSE cp "db:/tmp/${FILE}" "dumps/${FILE}"
$COMPOSE exec -T db rm -f "/tmp/${FILE}"

echo "✔ 덤프 생성: dumps/${FILE}"
ls -lh "dumps/${FILE}" | awk '{print "  크기:", $5}'
echo "  복원 방법: dumps/RESTORE.md"
