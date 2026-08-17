#!/bin/sh
set -e

echo "Generating Prisma client..."
uv run prisma generate

echo "Applying pending Prisma migrations..."
uv run prisma migrate deploy

echo "Checking Prisma migration status after deploy..."
uv run prisma migrate status

echo "Seeding some mock information..."
uv run scripts/seed-all.py

echo "Starting application..."
exec uv run main.py
