#!/bin/bash
set -e

echo "========================================="
echo "Running Code Quality Checks..."
echo "========================================="

echo ""
echo "1. Running Ruff (Linting)..."
uv run ruff check .

echo ""
echo "2. Running Black (Code Formatting)..."
uv run black --check .

echo ""
echo "3. Running isort (Import Sorting)..."
uv run isort --check-only .

echo ""
echo "4. Running mypy (Type Checking)..."
uv run mypy .

echo ""
echo "========================================="
echo "Running Tests..."
echo "========================================="

echo ""
echo "5. Running pytest..."
uv run pytest --cov --cov-report=term-missing

echo ""
echo "========================================="
echo "All checks passed! ✅"
echo "========================================="
