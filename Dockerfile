# ----------------------------
# Builder Stage
# ----------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libatomic1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PRISMA_HOME_DIR=/app/.cache/prisma-python
ENV npm_config_cache=/app/.cache/npm

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev
RUN uv run prisma generate


# ----------------------------
# Runtime Stage
# ----------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libatomic1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && mkdir -p /app/Upload && chown -R appuser:appuser /app

ENV PRISMA_HOME_DIR=/app/.cache/prisma-python
ENV PATH="/app/.venv/bin:$PATH"
ENV UVICORN_RELOAD=false

COPY --from=builder --chown=appuser:appuser /app /app

COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

USER appuser

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
