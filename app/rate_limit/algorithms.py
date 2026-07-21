from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.rate_limit.config import RateLimitConfig, RateLimitRule
from app.rate_limit.exceptions import RateLimitStorageError
from app.rate_limit.storage import MemoryStorage, RateLimitResult, RateLimitStorage, RedisStorage

logger = logging.getLogger("rate_limit.algorithm")


class RateLimiter(ABC):
    def __init__(self, storage: RateLimitStorage, config: RateLimitConfig):
        self._storage = storage
        self._config = config

    @abstractmethod
    async def check(self, identifier: str, endpoint: str) -> RateLimitResult: ...

    async def reset(self, identifier: str, endpoint: str) -> None:
        key = self._make_key(identifier, endpoint)
        await self._storage.reset(key)

    def _make_key(self, identifier: str, endpoint: str) -> str:
        return f"{identifier}:{endpoint}"

    @property
    def storage(self) -> RateLimitStorage:
        return self._storage


class SlidingWindowCounter(RateLimiter):
    async def check(self, identifier: str, endpoint: str) -> RateLimitResult:
        rule = self._config.get_rule(endpoint, self._extract_role(identifier))
        key = self._make_key(identifier, endpoint)
        try:
            return await self._storage.check_and_increment(key, rule.limit, rule.window)
        except RateLimitStorageError:
            logger.warning("Storage failure for %s on %s — allowing request", identifier, endpoint)
            return RateLimitResult(
                allowed=True,
                limit=rule.limit,
                remaining=rule.limit,
                current_count=0,
                previous_count=0,
                reset_at=0,
            )

    def _extract_role(self, identifier: str) -> str | None:
        if identifier.startswith("role:"):
            return identifier[5:]
        return None


class TokenBucket(RateLimiter):
    async def check(self, identifier: str, endpoint: str) -> RateLimitResult:
        rule = self._config.get_rule(endpoint, self._extract_role(identifier))
        key = f"tb:{self._make_key(identifier, endpoint)}"

        storage = self._storage
        if isinstance(storage, RedisStorage):
            try:
                return await storage.check_token_bucket(key, rule.limit, rule.window)
            except RateLimitStorageError:
                logger.warning("Token bucket storage failure for %s — allowing", identifier)
                return RateLimitResult(
                    allowed=True,
                    limit=rule.limit,
                    remaining=rule.limit,
                    current_count=0,
                    previous_count=0,
                    reset_at=0,
                )
        else:
            return await storage.check_and_increment(key, rule.limit, rule.window)

    def _extract_role(self, identifier: str) -> str | None:
        if identifier.startswith("role:"):
            return identifier[5:]
        return None


def create_storage(backend: str, redis_url: str = "redis://localhost:6379/0", key_prefix: str = "rl") -> RateLimitStorage:
    if backend == "memory":
        return MemoryStorage(key_prefix=key_prefix)
    return RedisStorage(redis_url=redis_url, key_prefix=key_prefix)


def create_limiter(
    config: RateLimitConfig,
    algorithm: str = "sliding_window",
) -> RateLimiter:
    storage = create_storage(config.storage_backend, config.redis_url, config.key_prefix)
    if algorithm == "token_bucket":
        return TokenBucket(storage, config)
    return SlidingWindowCounter(storage, config)
