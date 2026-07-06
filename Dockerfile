FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libatomic1 \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Redirect Prisma's Node/binary cache into /app so it's captured in the single COPY below
ENV PRISMA_HOME_DIR="/app/.cache/prisma-python"
ENV npm_config_cache="/app/.cache/npm"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY prisma/ prisma/
RUN uv run prisma generate
COPY . .
RUN uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ca-certificates libatomic1 && \
    rm -rf /var/lib/apt/lists/*

# Set the SAME env var here so the runtime Prisma client looks in the right spot
ENV PRISMA_HOME_DIR="/app/.cache/prisma-python"

# Only ONE copy needed now — everything lives under /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    UVICORN_RELOAD="false"
EXPOSE 8000
CMD ["python", "main.py"]