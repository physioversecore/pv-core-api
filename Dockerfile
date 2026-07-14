# ----------------------------
# Builder Stage
# ----------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libatomic1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Prisma cache
ENV PRISMA_HOME_DIR=/app/.cache/prisma-python
ENV npm_config_cache=/app/.cache/npm

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy the full project
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# Generate Prisma Client
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

ENV PRISMA_HOME_DIR=/app/.cache/prisma-python
ENV PATH="/app/.venv/bin:$PATH"
ENV UVICORN_RELOAD=false

# Copy application from builder
COPY --from=builder /app /app

# Create entrypoint script
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
