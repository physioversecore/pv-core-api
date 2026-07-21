from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.rate_limit.exceptions import RateLimitStorageError
from app.rate_limit.lua_scripts import SLIDING_WINDOW_SCRIPT, TOKEN_BUCKET_SCRIPT

logger = logging.getLogger("rate_limit.storage")


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    current_count: int
    previous_count: int
    reset_at: float
    retry_after: int = 0


class RateLimitStorage(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def is_connected(self) -> bool: ...

    @abstractmethod
    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult: ...

    @abstractmethod
    async def get_remaining(self, key: str, limit: int, window: int) -> RateLimitResult: ...

    @abstractmethod
    async def reset(self, key: str) -> None: ...

    @abstractmethod
    async def get_ttl(self, key: str) -> int: ...


def make_window_key(prefix: str, identifier: str, endpoint: str, window_id: int) -> str:
    return f"{prefix}:{identifier}:{endpoint}:{window_id}"


def current_window_id(window: int) -> int:
    return int(time.time()) // window


def previous_window_id(window: int) -> int:
    return current_window_id(window) - 1


def window_weight(window: int) -> float:
    now = time.time()
    elapsed_in_window = now - (int(now) // window * window)
    return 1.0 - (elapsed_in_window / window)


def calculate_reset_at(window: int) -> float:
    now = time.time()
    current_wid = int(now) // window
    return float((current_wid + 1) * window)


class RedisStorage(RateLimitStorage):
    def __init__(self, redis_url: str, key_prefix: str = "rl"):
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._client = None
        self._sliding_window_sha = None
        self._token_bucket_sha = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            await self._client.ping()
            self._sliding_window_sha = await self._client.script_load(SLIDING_WINDOW_SCRIPT)
            self._token_bucket_sha = await self._client.script_load(TOKEN_BUCKET_SCRIPT)
            logger.info("Redis rate limit storage connected to %s", self._redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise RateLimitStorageError(f"Redis connection failed: {e}", cause=e) from e

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Redis rate limit storage disconnected")

    async def is_connected(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        if not self._client:
            raise RateLimitStorageError("Redis not connected")
        try:
            now = time.time()
            result = await self._client.evalsha(
                self._sliding_window_sha,
                1,
                self._key_prefix,
                key,
                str(limit),
                str(window),
                str(now),
            )
            allowed = bool(result[0])
            return RateLimitResult(
                allowed=allowed,
                limit=int(result[1]),
                remaining=int(result[2]),
                reset_at=float(result[3]),
                retry_after=int(result[4]),
                previous_count=int(result[5]),
                current_count=int(result[6]),
            )
        except Exception as e:
            logger.error("Redis sliding window error: %s", e)
            raise RateLimitStorageError(f"Sliding window check failed: {e}", cause=e) from e

    async def check_token_bucket(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        if not self._client:
            raise RateLimitStorageError("Redis not connected")
        try:
            now = time.time()
            result = await self._client.evalsha(
                self._token_bucket_sha,
                1,
                key,
                str(limit),
                str(window),
                str(now),
            )
            allowed = bool(result[0])
            return RateLimitResult(
                allowed=allowed,
                limit=int(result[1]),
                remaining=int(result[2]),
                reset_at=float(result[3]),
                retry_after=int(result[4]),
                previous_count=0,
                current_count=limit - int(result[2]) if allowed else limit,
            )
        except Exception as e:
            logger.error("Redis token bucket error: %s", e)
            raise RateLimitStorageError(f"Token bucket check failed: {e}", cause=e) from e

    async def get_remaining(self, key: str, limit: int, window: int) -> RateLimitResult:
        if not self._client:
            raise RateLimitStorageError("Redis not connected")
        try:
            now = time.time()
            current_wid = int(now) // window
            prev_wid = current_wid - 1
            current_key = f"{self._key_prefix}:{key}:{current_wid}"
            prev_key = f"{self._key_prefix}:{key}:{prev_wid}"

            pipe = self._client.pipeline()
            pipe.get(current_key)
            pipe.get(prev_key)
            results = await pipe.execute()

            curr_count = int(results[0] or 0)
            prev_count = int(results[1] or 0)

            elapsed = now - (current_wid * window)
            weight = 1.0 - (elapsed / window)
            estimated = prev_count * weight + curr_count
            remaining = max(0, int(limit - estimated))
            reset_at = float((current_wid + 1) * window)

            return RateLimitResult(
                allowed=estimated < limit,
                limit=limit,
                remaining=remaining,
                current_count=curr_count,
                previous_count=prev_count,
                reset_at=reset_at,
            )
        except Exception as e:
            logger.error("Redis get_remaining error: %s", e)
            raise RateLimitStorageError(f"Get remaining failed: {e}", cause=e) from e

    async def reset(self, key: str) -> None:
        if not self._client:
            return
        try:
            pattern = f"{self._key_prefix}:{key}:*"
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error("Redis reset error for key %s: %s", key, e)

    async def get_ttl(self, key: str) -> int:
        if not self._client:
            return 0
        try:
            now = time.time()
            wid = int(now) // 60
            current_key = f"{self._key_prefix}:{key}:{wid}"
            return await self._client.ttl(current_key)
        except Exception:
            return 0

    async def get_active_keys(self) -> int:
        if not self._client:
            return 0
        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = await self._client.scan(cursor=cursor, match=f"{self._key_prefix}:*", count=100)
                count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception:
            return 0


class MemoryStorage(RateLimitStorage):
    def __init__(self, key_prefix: str = "rl"):
        self._key_prefix = key_prefix
        self._store: dict[str, int] = {}
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        logger.info("Memory rate limit storage connected (dev only)")

    async def disconnect(self) -> None:
        self._store.clear()
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        now = time.time()
        current_wid = int(now) // window
        prev_wid = current_wid - 1

        current_key = f"{self._key_prefix}:{key}:{current_wid}"
        prev_key = f"{self._key_prefix}:{key}:{prev_wid}"

        prev_count = self._store.get(prev_key, 0)

        elapsed = now - (current_wid * window)
        weight = 1.0 - (elapsed / window)
        estimated = prev_count * weight

        if estimated >= limit:
            reset_at = float((current_wid + 1) * window)
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                current_count=0,
                previous_count=prev_count,
                reset_at=reset_at,
                retry_after=max(1, int(reset_at - now)),
            )

        self._store[current_key] = self._store.get(current_key, 0) + 1
        curr_count = self._store[current_key]

        if estimated + curr_count > limit:
            self._store[current_key] -= 1
            reset_at = float((current_wid + 1) * window)
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                current_count=self._store[current_key],
                previous_count=prev_count,
                reset_at=reset_at,
                retry_after=max(1, int(reset_at - now)),
            )

        remaining = max(0, int(limit - (estimated + curr_count)))
        reset_at = float((current_wid + 1) * window)

        self._cleanup(window)

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            current_count=curr_count,
            previous_count=prev_count,
            reset_at=reset_at,
        )

    async def get_remaining(self, key: str, limit: int, window: int) -> RateLimitResult:
        now = time.time()
        current_wid = int(now) // window
        prev_wid = current_wid - 1

        current_key = f"{self._key_prefix}:{key}:{current_wid}"
        prev_key = f"{self._key_prefix}:{key}:{prev_wid}"

        curr_count = self._store.get(current_key, 0)
        prev_count = self._store.get(prev_key, 0)

        elapsed = now - (current_wid * window)
        weight = 1.0 - (elapsed / window)
        estimated = prev_count * weight + curr_count
        remaining = max(0, int(limit - estimated))
        reset_at = float((current_wid + 1) * window)

        return RateLimitResult(
            allowed=estimated < limit,
            limit=limit,
            remaining=remaining,
            current_count=curr_count,
            previous_count=prev_count,
            reset_at=reset_at,
        )

    async def reset(self, key: str) -> None:
        keys_to_delete = [k for k in self._store if k.startswith(f"{self._key_prefix}:{key}:")]
        for k in keys_to_delete:
            del self._store[k]

    async def get_ttl(self, key: str) -> int:
        return 0

    async def get_active_keys(self) -> int:
        return len(self._store)

    def _cleanup(self, window: int) -> None:
        now = time.time()
        current_wid = int(now) // window
        stale_threshold = current_wid - 2
        stale_keys = [k for k in self._store if int(k.rsplit(":", 1)[-1]) < stale_threshold]
        for k in stale_keys:
            del self._store[k]
