"""Recall@K / NDCG@K 순수 함수 테스트 (P0, §2)."""

import pytest

from apps.place.services.eval_service import compute_ndcg_at_k, compute_recall_at_k


class TestComputeRecallAtK:
    def test_perfect_recall(self) -> None:
        assert compute_recall_at_k([1, 2, 3], {1, 2, 3}, k=3) == 1.0

    def test_no_overlap(self) -> None:
        assert compute_recall_at_k([1, 2, 3], {4, 5}, k=3) == 0.0

    def test_partial_recall(self) -> None:
        assert compute_recall_at_k([1, 2, 3, 4], {1, 5}, k=3) == pytest.approx(0.5)

    def test_relevant_outside_k_not_counted(self) -> None:
        assert compute_recall_at_k([1, 2, 3, 4], {4}, k=2) == 0.0

    def test_empty_relevant_returns_zero(self) -> None:
        assert compute_recall_at_k([1, 2, 3], set(), k=3) == 0.0


class TestComputeNdcgAtK:
    def test_perfect_ndcg_when_all_relevant_at_top(self) -> None:
        assert compute_ndcg_at_k([1, 2], {1, 2}, k=2) == pytest.approx(1.0)

    def test_zero_when_no_overlap(self) -> None:
        assert compute_ndcg_at_k([1, 2, 3], {4, 5}, k=3) == 0.0

    def test_order_matters(self) -> None:
        # 정답이 1순위에 있을 때가 2순위에 있을 때보다 NDCG가 높다
        higher = compute_ndcg_at_k([1, 2], {1}, k=2)
        lower = compute_ndcg_at_k([2, 1], {1}, k=2)
        assert higher > lower
        assert higher == pytest.approx(1.0)

    def test_empty_relevant_returns_zero(self) -> None:
        assert compute_ndcg_at_k([1, 2, 3], set(), k=3) == 0.0

    def test_relevant_outside_k_not_counted(self) -> None:
        assert compute_ndcg_at_k([1, 2, 3], {3}, k=2) == 0.0
