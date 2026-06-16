"""데모/테스트용 시드 데이터 생성.

가상 유저(프로필·소셜 연동 포함), 팔로우 그래프, 유저 성향 벡터(travel_quiz.UserTestResult),
장소 리뷰(일부 이미지 포함), 북마크를 랜덤 생성한다.
여행 성향 유형(TravelType)은 `seed_travel_types`로 정식 8종을 적재하고, 유저별 유형은
실제 퀴즈와 동일하게 성향 벡터에서 파생한다(_determine_type_key).
장소(Place)·장소 이미지/운영정보/성향 벡터는 소스 데이터로 이미 적재돼 있다고 가정하고 건드리지 않는다.
데모 유저는 이메일 도메인 `@demo.local`로 식별하므로 재실행·정리가 가능하다.

    docker compose ... exec web uv run python manage.py seed_demo_data              # 생성
    docker compose ... exec web uv run python manage.py seed_demo_data --clear      # 삭제 후 재생성
    docker compose ... exec web uv run python manage.py seed_demo_data --delete     # 삭제만
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.bookmark.models import Bookmark
from apps.place.models import Place, Tag
from apps.review.models import Review
from apps.review.services.review_services import update_place_rating
from apps.travel_quiz.models import TravelType, UserTestResult
from apps.travel_quiz.services.travel_quiz_services import _determine_type_key
from apps.travel_quiz.services.travel_type_seeds import TRAVEL_TYPE_SEEDS
from apps.user.models import Follow, SocialUser, User

DEMO_EMAIL_DOMAIN = "demo.local"
DEMO_PASSWORD = "demo1234"
REVIEW_IMAGE_RATIO = 0.3  # 리뷰 중 이미지가 붙는 비율

REVIEW_CONTENTS: list[str] = [
    "분위기가 정말 좋았어요. 또 가고 싶네요.",
    "기대보다는 평범했어요. 사람이 너무 많아요.",
    "가족과 함께 다녀왔는데 만족스러웠습니다.",
    "주차가 조금 불편했지만 경치는 최고였어요.",
    "사진 찍기 좋은 곳! 인생샷 건졌습니다.",
    "조용하고 한적해서 힐링하기 딱이에요.",
    "재방문 의사 100%입니다. 강력 추천!",
    "음식이 맛있고 직원분들이 친절했어요.",
    "접근성이 좋아서 부담 없이 들르기 좋아요.",
    "가성비가 훌륭합니다. 추천해요.",
]

BIOS: list[str] = [
    "여행을 사랑하는 사람",
    "주말마다 어디론가 떠납니다",
    "맛집 탐방가",
    "사진과 풍경 수집가",
    "캠핑 러버",
    "전국 도장깨기 중",
    "느린 여행을 선호해요",
    "혼행 마스터",
]


class Command(BaseCommand):
    help = "데모용 가상 유저·팔로우·성향 벡터·리뷰 시드 데이터를 생성한다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--users", type=int, default=30, help="생성할 가상 유저 수")
        parser.add_argument("--reviews-per-user", type=int, default=15, help="유저당 평균 리뷰 수")
        parser.add_argument("--bookmarks-per-user", type=int, default=8, help="유저당 평균 북마크 수")
        parser.add_argument("--follows-per-user", type=int, default=5, help="유저당 평균 팔로우 수")
        parser.add_argument("--seed", type=int, default=42, help="난수 시드(재현용)")
        parser.add_argument(
            "--place-pool",
            type=int,
            default=120,
            help="리뷰·북마크가 몰리는 인기 장소 풀 크기(작을수록 장소당 개수가 많아지고 롱테일이 뚜렷해짐)",
        )
        parser.add_argument("--clear", action="store_true", help="기존 데모 데이터 삭제 후 재생성")
        parser.add_argument("--delete", action="store_true", help="데모 데이터 삭제만 (재생성 없음)")

    def handle(self, *args: Any, **options: Any) -> None:
        rng = random.Random(options["seed"])
        num_users: int = options["users"]
        reviews_per_user: int = options["reviews_per_user"]
        bookmarks_per_user: int = options["bookmarks_per_user"]
        follows_per_user: int = options["follows_per_user"]
        place_pool: int = options["place_pool"]

        if options["delete"]:
            self._clear()
            return

        if options["clear"]:
            self._clear()

        types_by_key = self._ensure_travel_types()
        tag_ids = list(Tag.objects.values_list("id", flat=True))
        place_ids = list(Place.objects.filter(is_active=True).values_list("id", flat=True))
        if not place_ids:
            self.stderr.write(self.style.ERROR("활성 장소가 없습니다. 먼저 장소 데이터를 적재하세요."))
            return

        # 리뷰·북마크가 인기 장소에 몰리도록 가중치 풀을 만든다(롱테일 분포). 둘이 풀을 공유해 인기 장소가 함께 쏠림.
        pool, pool_weights = self._build_place_popularity(rng, place_ids, place_pool)

        users = self._create_users(rng, num_users, tag_ids)
        self._create_social_users(rng, users)
        self._create_preferences(rng, users, types_by_key)
        self._create_follows(rng, users, follows_per_user)
        self._create_reviews(rng, users, pool, pool_weights, reviews_per_user)
        self._create_bookmarks(rng, users, pool, pool_weights, bookmarks_per_user)

        self.stdout.write(self.style.SUCCESS("데모 시드 완료"))

    # ── 단계별 헬퍼 ───────────────────────────────────────────────

    def _clear(self) -> None:
        demo_users = User.objects.filter(email__endswith=f"@{DEMO_EMAIL_DOMAIN}")
        place_ids = list(Review.objects.filter(user__in=demo_users).values_list("place_id", flat=True).distinct())
        count = demo_users.count()
        demo_users.delete()  # 리뷰·팔로우·성향치 CASCADE 삭제
        with transaction.atomic():
            for pid in place_ids:
                update_place_rating(pid)
        self.stdout.write(f"  정리: 데모 유저 {count}명 및 연관 데이터 삭제, 장소 {len(place_ids)}곳 평점 재계산")

    def _ensure_travel_types(self) -> dict[str, TravelType]:
        # 실제 유형 정의(8종, type_key = t/f 3글자)를 정식 시드 명령으로 적재한다.
        call_command("seed_travel_types")
        # 과거 데모용으로 임의 생성했던 비표준 유형이 있으면 정리한다.
        stray = TravelType.objects.exclude(type_key__in=TRAVEL_TYPE_SEEDS.keys())
        removed = stray.count()
        if removed:
            stray.delete()
            self.stdout.write(f"  여행 유형: 비표준 {removed}종 제거")
        types_by_key = {tt.type_key: tt for tt in TravelType.objects.all()}
        self.stdout.write(f"  여행 유형: {len(types_by_key)}종 준비")
        return types_by_key

    def _create_users(self, rng: random.Random, num_users: int, tag_ids: list[int]) -> list[User]:
        users: list[User] = []
        for i in range(num_users):
            email = f"demo{i:04d}@{DEMO_EMAIL_DOMAIN}"
            existing = User.objects.filter(email=email).first()
            if existing is not None:
                users.append(existing)
                continue
            birthday = date(1970, 1, 1) + timedelta(days=rng.randint(0, 36 * 365))
            user = User.objects.create_user(
                email=email,
                nickname=f"demo_{i:04d}",
                password=DEMO_PASSWORD,
                gender=rng.choice([User.Gender.MALE, User.Gender.FEMALE]),
                birthday=birthday.isoformat(),
                bio=rng.choice(BIOS),
                profile_img_url=f"https://i.pravatar.cc/300?u={email}",
            )
            if tag_ids:
                user.tags.set(rng.sample(tag_ids, k=min(len(tag_ids), rng.randint(2, 4))))
            users.append(user)
        self.stdout.write(f"  유저: {len(users)}명 준비 (비밀번호: {DEMO_PASSWORD})")
        return users

    def _create_preferences(self, rng: random.Random, users: list[User], types_by_key: dict[str, TravelType]) -> None:
        created = 0
        for user in users:
            vector = [round(rng.random(), 4) for _ in range(6)]
            # 실제 퀴즈와 동일하게 벡터에서 유형을 파생한다(활동성·사교성·공간지향 축).
            type_key = _determine_type_key(vector)
            _, is_created = UserTestResult.objects.update_or_create(
                user=user,
                defaults={"travel_type": types_by_key[type_key], "result_vector": vector},
            )
            created += int(is_created)
        self.stdout.write(f"  성향 벡터: {created}건 생성")

    def _create_follows(self, rng: random.Random, users: list[User], avg: int) -> None:
        follows: list[Follow] = []
        for user in users:
            candidates = [u for u in users if u.pk != user.pk]
            k = min(len(candidates), max(0, rng.randint(avg - 2, avg + 2)))
            for target in rng.sample(candidates, k):
                follows.append(Follow(follower=user, following=target))
        Follow.objects.bulk_create(follows, ignore_conflicts=True)
        total = Follow.objects.filter(follower__in=users).count()
        self.stdout.write(f"  팔로우: {total}건")

    def _create_reviews(
        self, rng: random.Random, users: list[User], pool: list[int], weights: list[float], avg: int
    ) -> None:
        reviews: list[Review] = []
        touched: set[int] = set()
        for user in users:
            count = max(1, rng.randint(avg - 5, avg + 5))
            for pid in self._weighted_sample(rng, pool, weights, count):  # 유저별 비복원 → unique(user, place) 보장
                rating = rng.choices([1, 2, 3, 4, 5], weights=[5, 10, 20, 35, 30])[0]
                image_url = (
                    f"https://picsum.photos/seed/r{user.pk}_{pid}/400/300"
                    if rng.random() < REVIEW_IMAGE_RATIO
                    else None
                )
                reviews.append(
                    Review(
                        user=user, place_id=pid, rating=rating, content=rng.choice(REVIEW_CONTENTS), image_url=image_url
                    )
                )
                touched.add(pid)
        Review.objects.bulk_create(reviews, ignore_conflicts=True, batch_size=1000)
        with transaction.atomic():
            for pid in touched:
                update_place_rating(pid)
        self.stdout.write(f"  리뷰: {len(reviews)}건 생성, 장소 {len(touched)}곳 평점 갱신")

    def _create_social_users(self, rng: random.Random, users: list[User]) -> None:
        created = 0
        for user in users:
            _, is_created = SocialUser.objects.get_or_create(
                user=user,
                provider=SocialUser.Provider.KAKAO,
                defaults={"provider_id": f"kakao_{rng.randint(10**9, 10**10 - 1)}"},
            )
            created += int(is_created)
        self.stdout.write(f"  소셜 계정(kakao): {created}건 생성")

    def _create_bookmarks(
        self, rng: random.Random, users: list[User], pool: list[int], weights: list[float], avg: int
    ) -> None:
        bookmarks: list[Bookmark] = []
        for user in users:
            count = max(1, rng.randint(avg - 3, avg + 3))
            for pid in self._weighted_sample(rng, pool, weights, count):  # 유저별 비복원 → unique(user, place) 보장
                bookmarks.append(Bookmark(user=user, place_id=pid))
        Bookmark.objects.bulk_create(bookmarks, ignore_conflicts=True, batch_size=1000)
        total = Bookmark.objects.filter(user__in=users).count()
        self.stdout.write(f"  북마크: {total}건")

    # ── 인기 가중 표본 ─────────────────────────────────────────────

    def _build_place_popularity(
        self, rng: random.Random, place_ids: list[int], pool_size: int
    ) -> tuple[list[int], list[float]]:
        """리뷰·북마크가 몰릴 인기 장소 풀과 Zipf형 가중치를 만든다(롱테일)."""
        pool = rng.sample(place_ids, min(pool_size, len(place_ids)))
        rng.shuffle(pool)  # 순위가 특정 장소에 고정되지 않도록 섞음
        weights = [1.0 / ((rank + 1) ** 0.8) for rank in range(len(pool))]
        return pool, weights

    @staticmethod
    def _weighted_sample(rng: random.Random, pool: list[int], weights: list[float], k: int) -> list[int]:
        """가중치 기반 비복원 표본 상위 k (Efraimidis–Spirakis A-Res). 가중이 클수록 자주 뽑힘."""
        k = min(k, len(pool))
        keyed = sorted((rng.random() ** (1.0 / w), pid) for pid, w in zip(pool, weights, strict=True))
        return [pid for _, pid in keyed[-k:]]
