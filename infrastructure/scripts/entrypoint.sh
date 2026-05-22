#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
/app/infrastructure/scripts/wait-for-it.sh db:5432 --timeout=60 --strict -- echo "PostgreSQL is ready"

echo "Waiting for Redis..."
/app/infrastructure/scripts/wait-for-it.sh redis:6379 --timeout=60 --strict -- echo "Redis is ready"

echo "Running migrations..."
uv run python manage.py migrate --noinput

echo "Collecting static files..."
uv run python manage.py collectstatic --noinput --clear

echo "Starting server..."
exec "$@"