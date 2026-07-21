from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rate_limit.access_list import AccessListManager
from app.rate_limit.algorithms import SlidingWindowCounter, TokenBucket, create_limiter, create_storage
from app.rate_limit.config import (
    DEFAULT_ENDPOINT_RULES,
    DEFAULT_ROLE_RULES,
    RateLimitConfig,
    RateLimitRule,
    build_config,
)
from app.rate_limit.dependencies import get_rate_limiter, rate_limit, set_rate_limiter
from app.rate_limit.exceptions import RateLimitExceeded, RateLimitStorageError
from app.rate_limit.log import log_request
from app.rate_limit.metrics import MetricsCollector, RateLimitMetrics
from app.rate_limit.storage import MemoryStorage, RateLimitResult, RateLimitStorage


class TestRateLimitRule:
    def test_valid_rule(self):
        rule = RateLimitRule(limit=100, window=60)
        assert rule.limit == 100
        assert rule.window == 60

    def test_rule_with_burst(self):
        rule = RateLimitRule(limit=100, window=60, burst=120)
        assert rule.burst == 120

    def test_negative_limit_raises(self):
        with pytest.raises(ValueError, match="limit must be >= 0"):
            RateLimitRule(limit=-1, window=60)

    def test_zero_window_raises(self):
        with pytest.raises(ValueError, match="window must be > 0"):
            RateLimitRule(limit=100, window=0)

    def test_negative_burst_raises(self):
        with pytest.raises(ValueError, match="burst must be >= 0"):
            RateLimitRule(limit=100, window=60, burst=-1)


class TestRateLimitConfig:
    def test_default_rule(self):
        config = RateLimitConfig()
        rule = config.get_rule("/api/v1/unknown")
        assert rule.limit == 100
        assert rule.window == 60

    def test_endpoint_exact_match(self):
        config = RateLimitConfig(
            endpoint_rules={
                "/api/v1/auth/login": RateLimitRule(limit=20, window=60),
            }
        )
        rule = config.get_rule("/api/v1/auth/login")
        assert rule.limit == 20

    def test_endpoint_wildcard_match(self):
        config = RateLimitConfig(
            endpoint_rules={
                "/api/v1/admin/*": RateLimitRule(limit=500, window=60),
            }
        )
        rule = config.get_rule("/api/v1/admin/users")
        assert rule.limit == 500

    def test_role_based_override(self):
        config = RateLimitConfig(
            role_rules={
                "ADMIN": RateLimitRule(limit=1000, window=60),
            }
        )
        rule = config.get_rule("/api/v1/sessions", role="ADMIN")
        assert rule.limit == 1000

    def test_role_takes_precedence_over_endpoint(self):
        config = RateLimitConfig(
            endpoint_rules={
                "/api/v1/sessions": RateLimitRule(limit=50, window=60),
            },
            role_rules={
                "ADMIN": RateLimitRule(limit=1000, window=60),
            },
        )
        rule = config.get_rule("/api/v1/sessions", role="ADMIN")
        assert rule.limit == 1000

    def test_build_config_defaults(self):
        config = build_config()
        assert config.enabled is True
        assert config.default_rule.limit == 100
        assert config.default_rule.window == 60

    def test_build_config_custom(self):
        config = build_config(
            default_limit=50,
            default_window=30,
            enabled=False,
        )
        assert config.default_rule.limit == 50
        assert config.default_rule.window == 30
        assert config.enabled is False


class TestMemoryStorage:
    @pytest.fixture
    def storage(self):
        return MemoryStorage(key_prefix="test_rl")

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, storage):
        await storage.connect()
        assert await storage.is_connected()
        await storage.disconnect()
        assert not await storage.is_connected()

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, storage):
        await storage.connect()
        result = await storage.check_and_increment("user:1", limit=5, window=60)
        assert result.allowed is True
        assert result.remaining == 4
        assert result.current_count == 1
        assert result.limit == 5

    @pytest.mark.asyncio
    async def test_increment_up_to_limit(self, storage):
        await storage.connect()
        for i in range(5):
            result = await storage.check_and_increment("user:1", limit=5, window=60)
        result = await storage.check_and_increment("user:1", limit=5, window=60)
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_separate_keys_independent(self, storage):
        await storage.connect()
        r1 = await storage.check_and_increment("user:1", limit=2, window=60)
        r2 = await storage.check_and_increment("user:2", limit=2, window=60)
        assert r1.allowed is True
        assert r2.allowed is True

    @pytest.mark.asyncio
    async def test_reset_clears_key(self, storage):
        await storage.connect()
        await storage.check_and_increment("user:1", limit=2, window=60)
        await storage.check_and_increment("user:1", limit=2, window=60)
        await storage.reset("user:1")
        result = await storage.check_and_increment("user:1", limit=2, window=60)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_get_remaining(self, storage):
        await storage.connect()
        await storage.check_and_increment("user:1", limit=5, window=60)
        result = await storage.get_remaining("user:1", limit=5, window=60)
        assert result.remaining == 4
        assert result.current_count == 1

    @pytest.mark.asyncio
    async def test_get_ttl_returns_zero(self, storage):
        await storage.connect()
        ttl = await storage.get_ttl("user:1")
        assert ttl == 0

    @pytest.mark.asyncio
    async def test_get_active_keys(self, storage):
        await storage.connect()
        await storage.check_and_increment("user:1", limit=5, window=60)
        await storage.check_and_increment("user:2", limit=5, window=60)
        count = await storage.get_active_keys()
        assert count == 2

    @pytest.mark.asyncio
    async def test_sliding_window_weight_calculation(self, storage):
        await storage.connect()
        now = time.time()
        current_wid = int(now) // 60
        prev_key = f"test_rl:user:1:{current_wid - 1}"
        storage._store[prev_key] = 8

        result = await storage.check_and_increment("user:1", limit=10, window=60)
        assert result.previous_count == 8
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_boundary_at_window_start(self, storage):
        await storage.connect()
        for i in range(10):
            await storage.check_and_increment("user:1", limit=10, window=60)
        result = await storage.check_and_increment("user:1", limit=10, window=60)
        assert result.allowed is False
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale_keys(self, storage):
        await storage.connect()
        now = time.time()
        current_wid = int(now) // 60
        storage._store[f"test_rl:user:1:{current_wid - 10}"] = 5
        storage._store[f"test_rl:user:1:{current_wid}"] = 3
        await storage.check_and_increment("user:1", limit=100, window=60)
        assert f"test_rl:user:1:{current_wid - 10}" not in storage._store


class TestSlidingWindowCounter:
    @pytest.fixture
    def limiter(self):
        storage = MemoryStorage(key_prefix="test_sw")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=5, window=60),
            endpoint_rules={
                "/api/v1/auth/login": RateLimitRule(limit=2, window=60),
            },
        )
        return SlidingWindowCounter(storage, config)

    @pytest.mark.asyncio
    async def test_allows_within_limit(self, limiter):
        for _ in range(4):
            result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is True
        assert result.remaining == 1

    @pytest.mark.asyncio
    async def test_blocks_at_limit(self, limiter):
        for _ in range(5):
            await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is False
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_endpoint_specific_limit(self, limiter):
        await limiter.check("ip:127.0.0.1", "/api/v1/auth/login")
        await limiter.check("ip:127.0.0.1", "/api/v1/auth/login")
        result = await limiter.check("ip:127.0.0.1", "/api/v1/auth/login")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_different_endpoints_independent(self, limiter):
        for _ in range(5):
            await limiter.check("ip:127.0.0.1", "/api/v1/auth/login")
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_reset_allows_again(self, limiter):
        for _ in range(5):
            await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        await limiter.reset("ip:127.0.0.1", "/api/v1/sessions")
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_storage_failure_allows_request(self, limiter):
        limiter._storage.check_and_increment = AsyncMock(side_effect=RateLimitStorageError("Redis down"))
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is True
        assert result.remaining == limiter._config.default_rule.limit

    @pytest.mark.asyncio
    async def test_role_based_limit(self):
        storage = MemoryStorage(key_prefix="test_role")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=5, window=60),
            role_rules={
                "ADMIN": RateLimitRule(limit=100, window=60),
            },
        )
        limiter = SlidingWindowCounter(storage, config)
        for _ in range(5):
            result = await limiter.check("role:ADMIN", "/api/v1/sessions")
        assert result.allowed is True
        assert result.remaining == 95

    @pytest.mark.asyncio
    async def test_different_clients_independent(self, limiter):
        for _ in range(5):
            await limiter.check("ip:10.0.0.1", "/api/v1/sessions")
        result = await limiter.check("ip:10.0.0.2", "/api/v1/sessions")
        assert result.allowed is True


class TestAccessListManager:
    def test_whitelist_default_empty(self):
        mgr = AccessListManager()
        assert not mgr.is_whitelisted("ip:127.0.0.1")

    def test_blacklist_default_empty(self):
        mgr = AccessListManager()
        assert not mgr.is_blacklisted("ip:127.0.0.1")

    def test_add_whitelist(self):
        mgr = AccessListManager()
        mgr.add_whitelist("ip:127.0.0.1")
        assert mgr.is_whitelisted("ip:127.0.0.1")

    def test_add_blacklist(self):
        mgr = AccessListManager()
        mgr.add_blacklist("ip:127.0.0.1")
        assert mgr.is_blacklisted("ip:127.0.0.1")

    def test_remove_whitelist(self):
        mgr = AccessListManager()
        mgr.add_whitelist("ip:127.0.0.1")
        assert mgr.remove_whitelist("ip:127.0.0.1")
        assert not mgr.is_whitelisted("ip:127.0.0.1")

    def test_remove_blacklist(self):
        mgr = AccessListManager()
        mgr.add_blacklist("ip:127.0.0.1")
        assert mgr.remove_blacklist("ip:127.0.0.1")
        assert not mgr.is_blacklisted("ip:127.0.0.1")

    def test_whitelist_ttl(self):
        mgr = AccessListManager()
        mgr.add_whitelist("ip:127.0.0.1", ttl=1)
        assert mgr.is_whitelisted("ip:127.0.0.1")

    def test_whitelist_expired(self):
        mgr = AccessListManager()
        mgr.add_whitelist("ip:127.0.0.1", ttl=-1)
        assert not mgr.is_whitelisted("ip:127.0.0.1")

    def test_blacklist_expired(self):
        mgr = AccessListManager()
        mgr.add_blacklist("ip:127.0.0.1", ttl=-1)
        assert not mgr.is_blacklisted("ip:127.0.0.1")

    def test_cleanup_removes_expired(self):
        mgr = AccessListManager()
        mgr.add_whitelist("ip:1.1.1.1", ttl=-1)
        mgr.add_blacklist("ip:2.2.2.2", ttl=-1)
        mgr.add_whitelist("ip:3.3.3.3")
        mgr.cleanup()
        assert mgr.whitelist_count == 1
        assert mgr.blacklist_count == 0

    def test_constructor_with_initial_sets(self):
        mgr = AccessListManager(
            whitelist={"ip:1.1.1.1"},
            blacklist={"ip:2.2.2.2"},
        )
        assert mgr.is_whitelisted("ip:1.1.1.1")
        assert mgr.is_blacklisted("ip:2.2.2.2")


class TestMetricsCollector:
    def test_record_allowed(self):
        m = MetricsCollector()
        m.record_allowed()
        m.record_allowed()
        assert m.metrics.requests_allowed == 2

    def test_record_blocked(self):
        m = MetricsCollector()
        m.record_blocked()
        assert m.metrics.requests_blocked == 1

    def test_record_redis_error(self):
        m = MetricsCollector()
        m.record_redis_error()
        assert m.metrics.redis_errors == 1

    def test_record_redis_latency(self):
        m = MetricsCollector()
        m.record_redis_latency(1.5)
        m.record_redis_latency(2.5)
        assert m.metrics.avg_redis_latency_ms == 2.0

    def test_to_dict(self):
        m = MetricsCollector()
        m.record_allowed()
        d = m.metrics.to_dict()
        assert d["requests_allowed"] == 1
        assert "avg_redis_latency_ms" in d

    def test_to_prometheus(self):
        m = MetricsCollector()
        m.record_allowed()
        prom = m.metrics.to_prometheus()
        assert "rate_limit_requests_allowed 1" in prom
        assert "# HELP rate_limit_requests_allowed" in prom

    def test_reset(self):
        m = MetricsCollector()
        m.record_allowed()
        m.record_blocked()
        m.reset()
        assert m.metrics.requests_allowed == 0
        assert m.metrics.requests_blocked == 0

    def test_set_active_keys(self):
        m = MetricsCollector()
        m.set_active_keys(42)
        assert m.metrics.active_keys == 42


class TestCreateStorage:
    def test_memory_backend(self):
        storage = create_storage("memory")
        assert isinstance(storage, MemoryStorage)

    def test_redis_backend(self):
        storage = create_storage("redis", redis_url="redis://localhost:6379/0")
        assert storage.__class__.__name__ == "RedisStorage"


class TestCreateLimiter:
    def test_sliding_window(self):
        config = build_config(storage_backend="memory")
        limiter = create_limiter(config, algorithm="sliding_window")
        assert isinstance(limiter, SlidingWindowCounter)

    def test_token_bucket(self):
        config = build_config(storage_backend="memory")
        limiter = create_limiter(config, algorithm="token_bucket")
        assert isinstance(limiter, TokenBucket)


class TestTokenBucket:
    @pytest.fixture
    def limiter(self):
        storage = MemoryStorage(key_prefix="test_tb")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=5, window=60),
        )
        return TokenBucket(storage, config)

    @pytest.mark.asyncio
    async def test_allows_first_request(self, limiter):
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_depletes_tokens(self, limiter):
        for _ in range(5):
            result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is False


class TestRateLimitResult:
    def test_result_fields(self):
        r = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=95,
            current_count=5,
            previous_count=10,
            reset_at=1000.0,
            retry_after=0,
        )
        assert r.allowed is True
        assert r.remaining == 95
        assert r.retry_after == 0

    def test_result_default_retry_after(self):
        r = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            current_count=100,
            previous_count=0,
            reset_at=1000.0,
        )
        assert r.retry_after == 0


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_requests_within_limit(self):
        storage = MemoryStorage(key_prefix="test_conc")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=10, window=60),
        )
        limiter = SlidingWindowCounter(storage, config)

        results = await asyncio.gather(
            *[limiter.check("ip:127.0.0.1", "/api/v1/sessions") for _ in range(10)]
        )
        allowed = sum(1 for r in results if r.allowed)
        blocked = sum(1 for r in results if not r.allowed)
        assert allowed == 10
        assert blocked == 0

    @pytest.mark.asyncio
    async def test_concurrent_requests_exceed_limit(self):
        storage = MemoryStorage(key_prefix="test_conc2")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=5, window=60),
        )
        limiter = SlidingWindowCounter(storage, config)

        results = await asyncio.gather(
            *[limiter.check("ip:127.0.0.1", "/api/v1/sessions") for _ in range(10)]
        )
        allowed = sum(1 for r in results if r.allowed)
        assert allowed == 5


class TestBuildConfig:
    def test_custom_endpoint_rules(self):
        rules = {"/api/v1/custom": RateLimitRule(limit=10, window=10)}
        config = build_config(endpoint_rules=rules)
        rule = config.get_rule("/api/v1/custom")
        assert rule.limit == 10

    def test_custom_role_rules(self):
        rules = {"MODERATOR": RateLimitRule(limit=300, window=60)}
        config = build_config(role_rules=rules)
        rule = config.get_rule("/api/v1/sessions", role="MODERATOR")
        assert rule.limit == 300

    def test_whitelist_blacklist(self):
        config = build_config(
            whitelist={"ip:1.1.1.1"},
            blacklist={"ip:2.2.2.2"},
        )
        assert "ip:1.1.1.1" in config.whitelist
        assert "ip:2.2.2.2" in config.blacklist


class TestLogRequest:
    def test_log_allowed(self):
        log_request(
            identifier="ip:127.0.0.1",
            endpoint="/api/v1/sessions",
            allowed=True,
            remaining=95,
            limit=100,
            response_time_ms=1.5,
        )

    def test_log_blocked(self):
        log_request(
            identifier="ip:127.0.0.1",
            endpoint="/api/v1/sessions",
            allowed=False,
            remaining=0,
            limit=100,
            response_time_ms=1.5,
            block_reason="limit_exceeded",
            client_ip="127.0.0.1",
        )


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_zero_limit(self):
        storage = MemoryStorage(key_prefix="test_zero")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=0, window=60),
        )
        limiter = SlidingWindowCounter(storage, config)
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_very_small_window(self):
        storage = MemoryStorage(key_prefix="test_small")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=100, window=1),
        )
        limiter = SlidingWindowCounter(storage, config)
        for _ in range(100):
            await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_very_large_limit(self):
        storage = MemoryStorage(key_prefix="test_large")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=1000000, window=60),
        )
        limiter = SlidingWindowCounter(storage, config)
        for _ in range(999999):
            await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        result = await limiter.check("ip:127.0.0.1", "/api/v1/sessions")
        assert result.allowed is True
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_empty_identifier(self):
        storage = MemoryStorage(key_prefix="test_empty_id")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=5, window=60),
        )
        limiter = SlidingWindowCounter(storage, config)
        result = await limiter.check("", "/api/v1/sessions")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_empty_endpoint(self):
        storage = MemoryStorage(key_prefix="test_empty_ep")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=5, window=60),
        )
        limiter = SlidingWindowCounter(storage, config)
        result = await limiter.check("ip:127.0.0.1", "")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_special_characters_in_key(self):
        storage = MemoryStorage(key_prefix="test_special")
        config = RateLimitConfig(
            default_rule=RateLimitRule(limit=5, window=60),
        )
        limiter = SlidingWindowCounter(storage, config)
        result = await limiter.check("user@test.com", "/api/v1/sessions")
        assert result.allowed is True


class TestDefaultEndpointRules:
    def test_login_limit(self):
        rule = DEFAULT_ENDPOINT_RULES["/api/v1/auth/login"]
        assert rule.limit == 20
        assert rule.window == 60

    def test_signup_limit(self):
        rule = DEFAULT_ENDPOINT_RULES["/api/v1/auth/signup"]
        assert rule.limit == 10

    def test_admin_wildcard(self):
        rule = DEFAULT_ENDPOINT_RULES["/api/v1/admin/*"]
        assert rule.limit == 500

    def test_payments_limit(self):
        rule = DEFAULT_ENDPOINT_RULES["/api/v1/payments"]
        assert rule.limit == 30


class TestDefaultRoleRules:
    def test_admin_role(self):
        rule = DEFAULT_ROLE_RULES["ADMIN"]
        assert rule.limit == 1000

    def test_therapist_role(self):
        rule = DEFAULT_ROLE_RULES["THERAPIST"]
        assert rule.limit == 200

    def test_patient_role(self):
        rule = DEFAULT_ROLE_RULES["PATIENT"]
        assert rule.limit == 100
