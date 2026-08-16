#!/bin/sh
set -e

echo "Generating Prisma client..."
uv run prisma generate

echo "Deploying Prisma migrations..."
uv run prisma migrate db push

echo "Prisma migrations and client generation completed."

echo "Starting Seeding On Mock Data..."
uv run scripts/seed-all.py

echo "Starting application..."
uv run main.py
