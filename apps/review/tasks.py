import io
import uuid
from typing import Any

import boto3
from celery import shared_task
from django.conf import settings
from PIL import Image

from apps.review.models import Review

_s3_client: Any = None


def _get_s3_client() -> Any:
    global _s3_client
    if _s3_client is None:  # 처음 한 번만 생성
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
    return _s3_client  # 이후엔 재사용


# Celery 사용 (사용자 요청 -> 서버가 태스크 큐에 넣음[Celery 워커가 백그라운드에서 압축 + S3 업로드] -> 즉시 응답 반환
# Celery 동작 구조 (Django서버[태스크 전달] -> Broker[Redis: 태스크 저장, 전달] -> Celery 워커[실제 실행])
@shared_task
def upload_review_image(review_id: int, image_data: bytes, content_type: str) -> None:
    """Pillow로 10MB이하로 압축, 이 함수를 Celery 워커가 백그라운드에서 실행, 서버는 이 태스크를 큐에 넣고 즉시 응답 반환"""
    image = Image.open(
        io.BytesIO(image_data)
    )  # bytes -> 파일 객체로 변환 (실제 파일을 디스크에 저장하지 않고, RAM에서 처리)
    fmt = "JPEG" if content_type == "image/jpeg" else "PNG"
    quality = 85
    output = io.BytesIO()

    if fmt == "JPEG":
        while True:
            output.seek(0)  # 커서를 초기화
            output.truncate()  # 이전 내용 삭제
            image.save(output, format="JPEG", quality=quality, optimize=True)
            if (
                output.tell() <= 10 * 1024 * 1024 or quality <= 10
            ):  # 10MB 이하면 완료, quality 10까지 줄여도 초과면 그냥 업로드
                break
            quality -= 10  # 10MB 초과면 quality 10씩 낮춰서 재시도
    # quality 85 → 저장 → 10MB 초과? → quality 75 → 저장 → 10MB 초과? → quality 65 → ... → 10MB 이하 또는 quality 10 → 업로드

    else:
        image.save(output, format="PNG", optimize=True)
        # PNG는 quality 파라미터가 없음 → 무손실 압축만 가능
        # JPEG처럼 루프 돌려봤자 결과가 안 바뀜 → 바로 저장

    if output.tell() > 10 * 1024 * 1024:
        raise ValueError("이미지를 10MB 이하로 압축할 수 없습니다.")
    # JPEG quality 10까지 줄여도 초과, 또는 PNG가 10MB 초과면 예외 발생
    # 이전 버전은 그냥 업로드했는데 요구사항 위반이라 수정됨

    """ S3 업로드 """
    ext = "jpg" if fmt == "JPEG" else "png"
    key = f"reviews/{uuid.uuid4()}.{ext}"  # 충돌 방지용 고유 파일명 생성

    output.seek(0)  # ← 반드시 필요 압축 후 커서가 파일 끝에 있어서 seek(0) 없이 업로드하면 빈 파일이 올라감
    _get_s3_client().upload_fileobj(
        output,  # 메모리의 이미지 데이터
        settings.AWS_STORAGE_BUCKET_NAME,
        key,
        ExtraArgs={
            "ContentType": f"image/{ext}"
        },  # S3에 파일 타입을 알려줌, 없으면 브라우저가 이미지를 다운로드로 처리 할  있음
    )

    """ Review image_url 업데이트 """
    image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}" f".s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{key}"
    Review.objects.filter(pk=review_id).update(image_url=image_url)
    # get() 방식과 비교
    # Review.objects.get(pk=review_id)  → 객체를 메모리에 올림 → .save() → 전체 컬럼 UPDATE
    # filter().update()                 → 객체 메모리 적재 없음 → 해당 컬럼만 UPDATE
