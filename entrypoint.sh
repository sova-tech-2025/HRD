#!/bin/sh
set -e

echo "Running alembic migrations..."
alembic upgrade head

echo "Starting bot..."
exec python -m bot
