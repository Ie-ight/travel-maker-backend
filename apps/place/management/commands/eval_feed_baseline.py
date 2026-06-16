"""S1(인기순) 추천 베이스라인 평가 management command (P0, §2).

시간 분할 평가: 각 유저의 북마크/리뷰(4점 이상) 중 `--cutoff-days` 이전 데이터로
전역 인기 후보(top-K)를 만들고, 그 이후 데이터를 held-out 정답으로 Recall@K/NDCG@K를 측정한다.

    docker compose ... exec web uv run python manage.py eval_feed_baseline \
        --cutoff-days 30 --k 20 --settings=config.settings.local
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Count
from django.utils import timezone

from apps.bookmark.models import Bookmark
from apps.place.services.eval_service import compute_ndcg_at_k, compute_recall_at_k
from apps.review.models import Review

#: 리뷰를 "긍정 신호"로 볼 평점 하한(§5.1의 4점 이상 가중치와 일치)
POSITIVE_REVIEW_RATING_THRESHOLD = 4


def _build_popularity_candidates(cutoff: datetime, k: int) -> list[int]:
    """cutoff 이전 북마크/긍정 리뷰 수를 합산해 인기 top-K 장소 ID를 반환한다."""
    counts: dict[int, int] = defaultdict(int)

    for row in Bookmark.objects.filter(created_at__lt=cutoff).values("place_id").annotate(c=Count("id")):
        counts[row["place_id"]] += row["c"]

    for row in (
        Review.objects.filter(created_at__lt=cutoff, rating__gte=POSITIVE_REVIEW_RATING_THRESHOLD)
        .values("place_id")
        .annotate(c=Count("id"))
    ):
        counts[row["place_id"]] += row["c"]

    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [place_id for place_id, _ in ordered[:k]]


def _build_holdouts(cutoff: datetime) -> dict[int, set[int]]:
    """cutoff 이후 북마크/긍정 리뷰를 유저별 held-out 정답 집합으로 반환한다."""
    holdouts: dict[int, set[int]] = defaultdict(set)

    for user_id, place_id in Bookmark.objects.filter(created_at__gte=cutoff).values_list("user_id", "place_id"):
        holdouts[user_id].add(place_id)

    for user_id, place_id in Review.objects.filter(
        created_at__gte=cutoff, rating__gte=POSITIVE_REVIEW_RATING_THRESHOLD
    ).values_list("user_id", "place_id"):
        holdouts[user_id].add(place_id)

    return holdouts


class Command(BaseCommand):
    help = "S1(인기순) 추천 베이스라인의 Recall@K/NDCG@K를 시간 분할 평가로 측정한다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--cutoff-days", type=int, default=30, help="held-out 기준 일수(기본 30일)")
        parser.add_argument("--k", type=int, default=20, help="Recall@K/NDCG@K의 K (기본 20)")
        parser.add_argument("--min-holdout", type=int, default=1, help="평가 대상 유저의 최소 held-out 개수(기본 1)")

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff_days: int = options["cutoff_days"]
        k: int = options["k"]
        min_holdout: int = options["min_holdout"]
        cutoff = timezone.now() - timedelta(days=cutoff_days)

        candidate_ids = _build_popularity_candidates(cutoff, k)
        if not candidate_ids:
            self.stdout.write(self.style.WARNING("컷오프 이전 데이터가 없어 인기 후보를 생성할 수 없습니다."))
            return

        holdouts = _build_holdouts(cutoff)
        evaluated = [relevant for relevant in holdouts.values() if len(relevant) >= min_holdout]

        if not evaluated:
            self.stdout.write(self.style.WARNING("--min-holdout 조건을 만족하는 유저가 없습니다."))
            return

        recalls = [compute_recall_at_k(candidate_ids, relevant, k) for relevant in evaluated]
        ndcgs = [compute_ndcg_at_k(candidate_ids, relevant, k) for relevant in evaluated]

        self.stdout.write(self.style.SUCCESS("S1(인기순) 베이스라인 평가 결과"))
        self.stdout.write(f"  cutoff: {cutoff_days}일 전 / k={k} / min_holdout={min_holdout}")
        self.stdout.write(f"  평가 유저 수: {len(evaluated)}")
        self.stdout.write(f"  Recall@{k}: {sum(recalls) / len(recalls):.4f}")
        self.stdout.write(f"  NDCG@{k}: {sum(ndcgs) / len(ndcgs):.4f}")
