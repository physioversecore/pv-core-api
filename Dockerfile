FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY prisma/ prisma/
RUN uv run prisma generate

COPY . .

RUN uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
COPY --from=builder /root/.cache /root/.cache

ENV PATH="/app/.venv/bin:$PATH" \
    UVICORN_RELOAD="false"

EXPOSE 8000

CMD ["python", "main.py"]
