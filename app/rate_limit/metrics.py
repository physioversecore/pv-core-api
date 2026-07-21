from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RateLimitMetrics:
    requests_allowed: int = 0
    requests_blocked: int = 0
    redis_errors: int = 0
    storage_fallbacks: int = 0
    total_redis_latency_ms: float = 0.0
    redis_latency_samples: int = 0
    active_keys: int = 0
    whitelist_hits: int = 0
    blacklist_hits: int = 0

    @property
    def avg_redis_latency_ms(self) -> float:
        if self.redis_latency_samples == 0:
            return 0.0
        return self.total_redis_latency_ms / self.redis_latency_samples

    def to_dict(self) -> dict:
        return {
            "requests_allowed": self.requests_allowed,
            "requests_blocked": self.requests_blocked,
            "redis_errors": self.redis_errors,
            "storage_fallbacks": self.storage_fallbacks,
            "avg_redis_latency_ms": round(self.avg_redis_latency_ms, 3),
            "active_keys": self.active_keys,
            "whitelist_hits": self.whitelist_hits,
            "blacklist_hits": self.blacklist_hits,
        }

    def to_prometheus(self) -> str:
        lines = [
            "# HELP rate_limit_requests_allowed Total allowed requests",
            "# TYPE rate_limit_requests_allowed counter",
            f"rate_limit_requests_allowed {self.requests_allowed}",
            "# HELP rate_limit_requests_blocked Total blocked requests",
            "# TYPE rate_limit_requests_blocked counter",
            f"rate_limit_requests_blocked {self.requests_blocked}",
            "# HELP rate_limit_redis_errors Total Redis errors",
            "# TYPE rate_limit_redis_errors counter",
            f"rate_limit_redis_errors {self.redis_errors}",
            "# HELP rate_limit_storage_fallbacks Storage fallback activations",
            "# TYPE rate_limit_storage_fallbacks counter",
            f"rate_limit_storage_fallbacks {self.storage_fallbacks}",
            "# HELP rate_limit_redis_latency_ms Average Redis latency in ms",
            "# TYPE rate_limit_redis_latency_ms gauge",
            f"rate_limit_redis_latency_ms {self.avg_redis_latency_ms:.3f}",
            "# HELP rate_limit_active_keys Active rate limit keys",
            "# TYPE rate_limit_active_keys gauge",
            f"rate_limit_active_keys {self.active_keys}",
            "# HELP rate_limit_whitelist_hits Whitelist bypass hits",
            "# TYPE rate_limit_whitelist_hits counter",
            f"rate_limit_whitelist_hits {self.whitelist_hits}",
            "# HELP rate_limit_blacklist_hits Blacklist block hits",
            "# TYPE rate_limit_blacklist_hits counter",
            f"rate_limit_blacklist_hits {self.blacklist_hits}",
        ]
        return "\n".join(lines) + "\n"


class MetricsCollector:
    def __init__(self):
        self._metrics = RateLimitMetrics()
        self._lock = Lock()

    @property
    def metrics(self) -> RateLimitMetrics:
        return self._metrics

    def record_allowed(self) -> None:
        with self._lock:
            self._metrics.requests_allowed += 1

    def record_blocked(self) -> None:
        with self._lock:
            self._metrics.requests_blocked += 1

    def record_redis_error(self) -> None:
        with self._lock:
            self._metrics.redis_errors += 1

    def record_storage_fallback(self) -> None:
        with self._lock:
            self._metrics.storage_fallbacks += 1

    def record_redis_latency(self, latency_ms: float) -> None:
        with self._lock:
            self._metrics.total_redis_latency_ms += latency_ms
            self._metrics.redis_latency_samples += 1

    def set_active_keys(self, count: int) -> None:
        with self._lock:
            self._metrics.active_keys = count

    def record_whitelist_hit(self) -> None:
        with self._lock:
            self._metrics.whitelist_hits += 1

    def record_blacklist_hit(self) -> None:
        with self._lock:
            self._metrics.blacklist_hits += 1

    def reset(self) -> None:
        with self._lock:
            self._metrics = RateLimitMetrics()
