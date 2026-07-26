from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import db
from app.exceptions import register_exception_handlers
from app.logging_config import setup_logging, logger
from app.middleware import RequestIDMiddleware
from app.rate_limit import (
    build_config,
    create_limiter,
    set_rate_limiter,
)
from app.rate_limit.access_list import AccessListManager
from app.rate_limit.log import log_startup
from app.rate_limit.metrics import MetricsCollector
from app.rate_limit.middleware import RateLimitMiddleware

from app.routers import (
    admin_router,
    admin_extras_router,
    auth_router,
    availability_router,
    cart_router,
    earnings_router,
    patients_router,
    payments_router,
    products_router,
    reports_router,
    reviews_router,
    sessions_router,
    settings_router,
    therapists_router,
    uploads_router,
)

_limiter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _limiter
    setup_logging("production" if not settings.uvicorn_reload else "development")
    logger.info("application starting", extra={"port": settings.backend_port})

    await db.connect()
    logger.info("database connected")

    if settings.rate_limit_enabled:
        config = build_config(
            enabled=True,
            redis_url=settings.redis_url,
            storage_backend=settings.rate_limit_storage_backend,
            default_limit=settings.rate_limit_default_limit,
            default_window=settings.rate_limit_default_window,
        )
        _limiter = create_limiter(config)
        set_rate_limiter(_limiter)
        try:
            await _limiter.storage.connect()
            logger.info("rate limiter connected", extra={"backend": settings.rate_limit_storage_backend})
        except Exception:
            from app.rate_limit.config import RateLimitConfig, RateLimitRule
            from app.rate_limit.algorithms import SlidingWindowCounter
            from app.rate_limit.storage import MemoryStorage

            config.storage_backend = "memory"
            _limiter = SlidingWindowCounter(MemoryStorage(), config)
            set_rate_limiter(_limiter)
            await _limiter.storage.connect()
            log_startup(backend="memory", enabled=True)
            logger.warning("redis unavailable, falling back to memory rate limiting")
    else:
        log_startup(backend="none", enabled=False)

    yield

    logger.info("application shutting down")
    if _limiter:
        await _limiter.storage.disconnect()
    await db.disconnect()


app = FastAPI(
    title="Sahayatri Physio API",
    description="Backend API for the Sahayatri Physiotherapy platform.",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)

if settings.rate_limit_enabled:
    _rate_config = build_config(
        enabled=True,
        redis_url=settings.redis_url,
        storage_backend=settings.rate_limit_storage_backend,
        default_limit=settings.rate_limit_default_limit,
        default_window=settings.rate_limit_default_window,
    )
    app.add_middleware(
        RateLimitMiddleware,
        config=_rate_config,
        access_list=AccessListManager(),
        metrics=MetricsCollector(),
    )

app.include_router(auth_router, prefix="/api/v1")
app.include_router(patients_router, prefix="/api/v1")
app.include_router(therapists_router, prefix="/api/v1")
app.include_router(earnings_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(cart_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(admin_extras_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(availability_router, prefix="/api/v1")


@app.get("/health")
async def health():
    db_ok = False
    try:
        await db.execute_raw("SELECT 1")
        db_ok = True
    except Exception:
        pass

    redis_ok = False
    if _limiter and hasattr(_limiter, "storage") and hasattr(_limiter.storage, "_client"):
        try:
            await _limiter.storage._client.ping()
            redis_ok = True
        except Exception:
            pass

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else ("unavailable" if not settings.rate_limit_enabled else "error"),
        },
    }


@app.get("/live")
async def live():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    db_ok = False
    try:
        await db.execute_raw("SELECT 1")
        db_ok = True
    except Exception:
        pass
    if not db_ok:
        from starlette.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "not ready"})
    return {"status": "ready"}
