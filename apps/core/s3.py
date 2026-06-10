import io
import os
import uuid
from typing import Any

import boto3
from django.conf import settings
from PIL import Image

# Celery는 prefork(멀티프로세스)로 동작하기 때문에 global 단일 클라이언트를 쓰면
# fork 이후 자식 프로세스들이 같은 소켓/커넥션을 공유하게 되어 간헐적 연결 오류가 발생한다.
# PID별로 클라이언트를 분리해 각 프로세스가 독립적인 연결을 갖도록 한다.
_s3_clients: dict[int, Any] = {}
_MAX_SIZE = 10 * 1024 * 1024  # 10MB


def get_s3_client() -> Any:
    """현재 프로세스(PID)에 해당하는 S3 클라이언트를 반환한다. 처음 한 번만 생성 후 재사용."""
    pid = os.getpid()
    if pid not in _s3_clients:
        _s3_clients[pid] = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
    return _s3_clients[pid]


def delete_s3_object(key: str) -> None:
    """S3에서 특정 key의 파일을 삭제한다. 업로드 후 DB 저장 실패 시 고아 파일 정리용."""
    get_s3_client().delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)


def compress_and_upload(image_data: bytes, content_type: str, folder: str) -> tuple[str, str]:
    """이미지를 압축하고 S3에 업로드한다.

    - JPEG: quality 85부터 10 단위로 낮추며 10MB 이하가 될 때까지 재압축
    - PNG: 무손실 압축만 가능하므로 quality 루프 없이 바로 저장
    - RGBA/P 모드 이미지를 JPEG로 저장하면 오류가 발생하므로 RGB로 변환
    - image.verify() 로 손상된 파일을 사전 차단 (verify() 후에는 반드시 재오픈 필요)
    - 충돌 방지를 위해 파일명은 UUID로 생성
    - folder 파라미터로 앱별 S3 경로를 구분 (예: "reviews", "profiles")

    Returns:
        (key, url) — key는 S3 객체 경로, url은 접근 가능한 전체 URL
    """
    image = Image.open(io.BytesIO(image_data))
    image.verify()
    image = Image.open(io.BytesIO(image_data))  # verify() 후 재오픈 필요

    fmt = "JPEG" if content_type == "image/jpeg" else "PNG"

    if fmt == "JPEG" and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")  # type: ignore[assignment]

    output = io.BytesIO()

    if fmt == "JPEG":
        quality = 85
        while True:
            output.seek(0)  # 커서 초기화
            output.truncate()  # 이전 내용 삭제
            image.save(output, format="JPEG", quality=quality, optimize=True)
            if output.tell() <= _MAX_SIZE or quality <= 10:
                # 10MB 이하면 완료, quality 10까지 줄여도 초과면 그냥 업로드
                break
            quality -= 10  # 10MB 초과 시 quality 10씩 낮춰서 재시도
    else:
        image.save(output, format="PNG", optimize=True)
        # PNG는 quality 파라미터가 없어 무손실 압축만 가능 → 루프 없이 바로 저장

    if output.tell() > _MAX_SIZE:
        raise ValueError("이미지를 10MB 이하로 압축할 수 없습니다.")

    ext = "jpg" if fmt == "JPEG" else "png"
    key = f"{folder}/{uuid.uuid4()}.{ext}"  # 충돌 방지용 고유 파일명

    output.seek(0)  # 압축 후 커서가 파일 끝에 있으므로 seek(0) 필수, 없으면 빈 파일 업로드됨
    get_s3_client().upload_fileobj(
        output,
        settings.AWS_STORAGE_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": f"image/{ext}"},  # 없으면 브라우저가 이미지를 다운로드로 처리
    )

    url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{key}"
    return key, url
