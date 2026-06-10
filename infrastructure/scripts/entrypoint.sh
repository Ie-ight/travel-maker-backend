#!/bin/bash
set -e

echo "Waiting for postgres..."
/app/infrastructure/scripts/wait-for-it.sh db:5432 --timeout=30

echo "Running migrations..."
uv run python manage.py migrate --noinput

echo "Collecting static files..."
uv run python manage.py collectstatic --noinput

echo "Starting server..."
exec "$@"
