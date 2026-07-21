from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window: int
    identifier: str = "ip"
    burst: int | None = None

    def __post_init__(self):
        if self.limit < 0:
            raise ValueError(f"limit must be >= 0, got {self.limit}")
        if self.window <= 0:
            raise ValueError(f"window must be > 0, got {self.window}")
        if self.burst is not None and self.burst < 0:
            raise ValueError(f"burst must be >= 0, got {self.burst}")


@dataclass
class RateLimitConfig:
    enabled: bool = True
    default_rule: RateLimitRule = field(default_factory=lambda: RateLimitRule(limit=100, window=60))
    endpoint_rules: dict[str, RateLimitRule] = field(default_factory=dict)
    storage_backend: str = "redis"
    redis_url: str = "redis://localhost:6379/0"
    key_prefix: str = "rl"
    whitelist: set[str] = field(default_factory=set)
    blacklist: set[str] = field(default_factory=set)
    role_rules: dict[str, RateLimitRule] = field(default_factory=dict)
    trust_x_forwarded_for: bool = False

    def get_rule(self, endpoint: str, role: str | None = None) -> RateLimitRule:
        if role and role in self.role_rules:
            return self.role_rules[role]
        for pattern, rule in self.endpoint_rules.items():
            if self._matches(endpoint, pattern):
                return rule
        return self.default_rule

    @staticmethod
    def _matches(endpoint: str, pattern: str) -> bool:
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            return endpoint.startswith(prefix)
        if pattern.startswith("/*"):
            suffix = pattern[1:]
            return endpoint.endswith(suffix)
        return endpoint == pattern


DEFAULT_ENDPOINT_RULES: dict[str, RateLimitRule] = {
    "/api/v1/auth/login": RateLimitRule(limit=20, window=60),
    "/api/v1/auth/signup": RateLimitRule(limit=10, window=60),
    "/api/v1/sessions": RateLimitRule(limit=100, window=60),
    "/api/v1/admin/*": RateLimitRule(limit=500, window=60),
    "/api/v1/payments": RateLimitRule(limit=30, window=60),
    "/api/v1/cart": RateLimitRule(limit=60, window=60),
}

DEFAULT_ROLE_RULES: dict[str, RateLimitRule] = {
    "ADMIN": RateLimitRule(limit=1000, window=60),
    "THERAPIST": RateLimitRule(limit=200, window=60),
    "PATIENT": RateLimitRule(limit=100, window=60),
}


def build_config(
    enabled: bool = True,
    redis_url: str = "redis://localhost:6379/0",
    storage_backend: str = "redis",
    default_limit: int = 100,
    default_window: int = 60,
    endpoint_rules: dict[str, RateLimitRule] | None = None,
    role_rules: dict[str, RateLimitRule] | None = None,
    whitelist: set[str] | None = None,
    blacklist: set[str] | None = None,
    trust_x_forwarded_for: bool = False,
) -> RateLimitConfig:
    return RateLimitConfig(
        enabled=enabled,
        default_rule=RateLimitRule(limit=default_limit, window=default_window),
        endpoint_rules=endpoint_rules or DEFAULT_ENDPOINT_RULES,
        role_rules=role_rules or DEFAULT_ROLE_RULES,
        storage_backend=storage_backend,
        redis_url=redis_url,
        whitelist=whitelist or set(),
        blacklist=blacklist or set(),
        trust_x_forwarded_for=trust_x_forwarded_for,
    )
