#!/bin/sh
set -e

echo "Generating Prisma client..."
uv run prisma generate

echo "Running Prisma migrations..."

echo "Running Prisma migration dev fro crate migrations file..."
uv run prisma migrate dev

echo "Deploying Prisma migrations..."
uv run prisma migrate deploy

echo "Prisma migrations and client generation completed."

echo "Starting Seeding On Mock Data..."
uv run scripts/seed-all.py

echo "Starting application..."
uv run main.py
