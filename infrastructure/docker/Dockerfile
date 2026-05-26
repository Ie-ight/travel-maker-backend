# Python 3.12 베이스 이미지
FROM python:3.12-slim

# 환경변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 파일 복사
COPY pyproject.toml uv.lock ./

# Python을 /usr/local에 설치하도록 설정
RUN uv python install 3.12 && \
    uv sync --python /usr/local/bin/python3.12

# 프로젝트 파일 복사
COPY . .

# PATH에 .venv 추가
ENV PATH="/app/.venv/bin:$PATH"

# 스크립트 실행 권한 부여
RUN chmod +x /app/infrastructure/scripts/entrypoint.sh
RUN chmod +x /app/infrastructure/scripts/wait-for-it.sh

# 정적 파일 디렉토리 생성
RUN mkdir -p /app/staticfiles /app/media

# 포트 노출
EXPOSE 8000

# Entrypoint 스크립트 실행
ENTRYPOINT ["/app/infrastructure/scripts/entrypoint.sh"]
