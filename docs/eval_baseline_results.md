# 추천 피드 평가 베이스라인 (P0)

S1(인기순) 추천 베이스라인의 Recall@K/NDCG@K를 시간 분할 방식으로 측정한다.

- 방법: 각 유저의 북마크/리뷰(4점 이상) 중 `--cutoff-days`(기본 30일) 이전 데이터로 전역 인기 top-K
  후보를 생성하고, 그 이후 데이터를 held-out 정답으로 Recall@K/NDCG@K를 계산한다.
- 실행:
  ```bash
  docker compose -f infrastructure/docker/docker-compose.yml exec web sh -c \
    "uv run python manage.py eval_feed_baseline --cutoff-days 30 --k 20 --settings=config.settings.local"
  ```

## 결과

| 실행 시점 | cutoff-days | k | 평가 유저 수 | Recall@K | NDCG@K | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-06-15 | 30 | 20 | - | - | - | 현재 dev DB에는 30일 이상 된 북마크/리뷰 데이터가 없어 후보/held-out을 생성할 수 없음("컷오프 이전 데이터가 없어 인기 후보를 생성할 수 없습니다."). 운영 데이터 적재 후 재실행 필요. |

## S2/S3 비교 (P4 완료 후, §2.2)

P4(S3 임베딩 ANN) 완료 후, 동일 하네스를 S2(6축 ANN)/S3(임베딩 ANN) 후보 생성 로직으로 확장해
S1과 비교한다. 하드 스위치(§8 리스크)의 정량적 영향을 평가하는 데 사용한다. 이 비교는 운영
데이터(유저 행동 로그, 장소 임베딩 커버리지)가 누적된 후 수행한다.
