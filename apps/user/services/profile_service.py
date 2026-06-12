from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

from apps.bookmark.models import Bookmark
from apps.core.exceptions import Conflict
from apps.core.presigned_url.services import PresignedUrlService
from apps.review.models import Review
from apps.user.models import User


class BookmarkPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 20


class ReviewPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 20


class UserBookmarkService:
    @staticmethod
    def get_bookmarks(user: User, request: Request) -> tuple[list[Bookmark] | None, BookmarkPagination]:
        qs = (
            Bookmark.objects.filter(user=user)
            .select_related("place")
            .prefetch_related("place__images")
            .order_by("-created_at")
        )
        paginator = BookmarkPagination()
        page = paginator.paginate_queryset(qs, request)
        return page, paginator


class UserReviewService:
    @staticmethod
    def get_reviews(user: User, request: Request) -> tuple[list[Review] | None, ReviewPagination]:
        qs = Review.objects.filter(user=user).select_related("place").order_by("-created_at")
        paginator = ReviewPagination()
        page = paginator.paginate_queryset(qs, request)
        return page, paginator


class NicknameService:
    @staticmethod
    def check_available(nickname: str, exclude_user: User | None = None) -> None:
        qs = User.objects.filter(nickname=nickname)
        if exclude_user is not None:
            qs = qs.exclude(pk=exclude_user.pk)
        if qs.exists():
            raise Conflict("중복된 닉네임이 존재합니다.")


class ProfileImageService:
    @staticmethod
    def set_profile_image_url(user: User, img_url: str) -> None:
        old_img_url = user.profile_img_url
        user.profile_img_url = img_url
        user.save(update_fields=["profile_img_url"])

        if old_img_url and old_img_url != img_url:
            PresignedUrlService.delete_by_img_url(old_img_url)
