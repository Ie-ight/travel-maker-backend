"""행동 기반 개인화 피드(S1/S2/S3) 관련 수치 상수.

action_weight_service / user_content_vector_service / feed_stage_service 등에서
이 모듈의 상수를 import해 사용한다. 리터럴 값을 코드에 직접 쓰지 않는다.
P5(평가·튜닝) 시 이 파일의 값만 조정하면 된다.
"""

from typing import Final

# §6 명시적 행동 신호 가중치 (A값). 리뷰는 평점별로 분기, 3점은 중립(UserActionLog 생성 안 함)
REVIEW_WEIGHT_BY_RATING: Final[dict[int, float]] = {
    5: 1.0,
    4: 0.5,
    3: 0.0,
    2: -0.5,
    1: -0.5,
}
BOOKMARK_WEIGHT: Final[float] = 0.8
UNBOOKMARK_WEIGHT: Final[float] = -0.1
ROUTE_ADD_WEIGHT: Final[float] = 0.8

# §7 인기도 보정 공식: P = 1 / log10(review_count + bookmark_count + POPULARITY_LOG_OFFSET)
POPULARITY_LOG_OFFSET: Final[int] = 10

# §6.4 시간 감쇠 / 강등 윈도우
DEFAULT_DECAY_LAMBDA: Final[float] = 0.01
BEHAVIOR_LOOKBACK_DAYS: Final[int] = 90

# §0/§7.1 S2 → S3 전환 임계값 (action_count)
S3_ACTION_COUNT_THRESHOLD: Final[int] = 10

# §6.1 영벡터 안전장치
ZERO_VECTOR_NORM_EPSILON: Final[float] = 1e-8

# §7.2 태그 부스트 상한 (P5 튜닝 대상)
TAG_BOOST_CAP: Final[float] = 0.3
