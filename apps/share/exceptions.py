from apps.core.exceptions import NotFound


class ContentNotFound(NotFound):
    default_detail = "공유할 콘텐츠를 찾을 수 없습니다."
