#!/bin/sh
set -e

echo "Generating Prisma client..."
uv run prisma generate

echo "Checking Prisma migration status..."
uv run prisma migrate status

echo "Sleep for 5 sec "
sleep 5

echo "Applying pending Prisma migrations..."
uv run prisma migrate deploy

echo "Sleep for 5 sec "
sleep 5

echo " Seeding some mock information"
uv run scripts/seed-all.py

echo "Sleep for 5 sec "
sleep 5

echo "Starting application..."
uv run main.py
