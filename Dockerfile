FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app

# Add this block — installs the missing shared library Prisma's Node binary needs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ca-certificates libatomic1 && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY prisma/ prisma/
RUN uv run prisma generate

COPY . .
RUN uv sync --frozen --no-dev


COPY --from=builder /app /app
COPY --from=builder /root/.cache /root/.cache

ENV PATH="/app/.venv/bin:$PATH" \
    UVICORN_RELOAD="false"
    
EXPOSE 8000
CMD ["python", "main.py"]