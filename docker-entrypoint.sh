#!/bin/sh
set -e

echo "Generating Prisma client..."
uv run prisma generate

echo "Reseting Database and apply all migration"
uv run prisma migrate reset

echo "Applying all Pending Prisma migrations..."
uv run prisma migrate deploy

echo "Prisma migrations and client generation completed."

echo "Starting Seeding On Mock Data..."
uv run scripts/seed-all.py

echo "Starting application..."
uv run main.py
