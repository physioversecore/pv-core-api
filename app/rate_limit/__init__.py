from __future__ import annotations

import logging

from app.rate_limit.access_list import AccessListManager
from app.rate_limit.algorithms import (
    RateLimiter,
    SlidingWindowCounter,
    TokenBucket,
    create_limiter,
    create_storage,
)
from app.rate_limit.config import (
    DEFAULT_ENDPOINT_RULES,
    DEFAULT_ROLE_RULES,
    RateLimitConfig,
    RateLimitRule,
    build_config,
)
from app.rate_limit.dependencies import get_rate_limiter, rate_limit, set_rate_limiter
from app.rate_limit.exceptions import RateLimitExceeded, RateLimitStorageError
from app.rate_limit.log import log_request, log_startup, log_storage_error
from app.rate_limit.metrics import MetricsCollector, RateLimitMetrics
from app.rate_limit.middleware import RateLimitMiddleware
from app.rate_limit.storage import (
    MemoryStorage,
    RateLimitResult,
    RateLimitStorage,
    RedisStorage,
)

logger = logging.getLogger("rate_limit")

_global_metrics: MetricsCollector | None = None
_global_access_list: AccessListManager | None = None


def init_rate_limiting(
    app,
    config: RateLimitConfig,
    algorithm: str = "sliding_window",
) -> RateLimiter:
    global _global_metrics, _global_access_list

    _global_metrics = MetricsCollector()
    _global_access_list = AccessListManager(
        whitelist=config.whitelist,
        blacklist=config.blacklist,
    )

    limiter = create_limiter(config, algorithm)
    set_rate_limiter(limiter)

    log_startup(
        backend=config.storage_backend,
        redis_url=config.redis_url if config.storage_backend == "redis" else "",
        enabled=config.enabled,
    )

    return limiter


def get_global_metrics() -> MetricsCollector | None:
    return _global_metrics


def get_global_access_list() -> AccessListManager | None:
    return _global_access_list


__all__ = [
    "AccessListManager",
    "MetricsCollector",
    "MemoryStorage",
    "RateLimitConfig",
    "RateLimitExceeded",
    "RateLimitMetrics",
    "RateLimitMiddleware",
    "RateLimitResult",
    "RateLimitRule",
    "RateLimitStorage",
    "RateLimitStorageError",
    "RateLimiter",
    "RedisStorage",
    "SlidingWindowCounter",
    "TokenBucket",
    "build_config",
    "create_limiter",
    "create_storage",
    "get_global_access_list",
    "get_global_metrics",
    "get_rate_limiter",
    "init_rate_limiting",
    "log_request",
    "log_startup",
    "log_storage_error",
    "rate_limit",
    "set_rate_limiter",
]
