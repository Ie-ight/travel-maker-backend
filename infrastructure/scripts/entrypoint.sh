#!/bin/bash
set -e

echo "Waiting for postgres..."
/app/infrastructure/scripts/wait-for-it.sh db:5432 --timeout=30

echo "Running migrations..."
# 깨진 .venv 제거 (컨테이너 내부 볼륨만 영향, 호스트 무관)
if [ -d /app/.venv ] && ! /app/.venv/bin/python --version > /dev/null 2>&1; then
    rm -rf /app/.venv
fi
uv run python manage.py migrate --noinput

# 프로덕션 환경에서만 collectstatic 실행
if [ "$DJANGO_SETTINGS_MODULE" = "config.settings.prod" ]; then
    echo "Collecting static files..."
    uv run python manage.py collectstatic --noinput
else
    echo "Development mode: Skipping collectstatic"
fi

echo "Starting server..."
exec "$@"
