#!/bin/sh
set -e

echo "Running Prisma migrations..."
uv run prisma migrate deploy

echo "Generating Prisma client..."
uv run prisma generate

echo "Starting application..."
exec python main.py
