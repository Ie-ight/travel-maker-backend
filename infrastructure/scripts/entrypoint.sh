#!/bin/bash
set -e

echo "Waiting for postgres..."
/app/infrastructure/scripts/wait-for-it.sh db:5432 --timeout=30

echo "Running migrations..."
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
