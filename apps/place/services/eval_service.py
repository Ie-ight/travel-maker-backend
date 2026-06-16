"""추천 피드 평가 지표 (P0, §2). Recall@K / NDCG@K 순수 함수."""

import math


def compute_recall_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """추천 목록 상위 K개 중 held-out 정답(relevant)이 차지하는 비율. relevant가 비면 0.0."""
    if not relevant:
        return 0.0
    hits = len(set(recommended[:k]) & relevant)
    return hits / len(relevant)


def compute_ndcg_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """추천 목록 상위 K개의 NDCG. relevant가 비면 0.0."""
    if not relevant:
        return 0.0

    dcg = sum(1.0 / math.log2(i + 2) for i, place_id in enumerate(recommended[:k]) if place_id in relevant)

    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg == 0.0:
        return 0.0

    return dcg / idcg
