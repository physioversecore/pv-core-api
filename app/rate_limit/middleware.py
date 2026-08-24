from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.rate_limit.access_list import AccessListManager
from app.rate_limit.algorithms import RateLimiter
from app.rate_limit.config import RateLimitConfig
from app.rate_limit.log import log_request
from app.rate_limit.metrics import MetricsCollector

logger = logging.getLogger("rate_limit.middleware")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        config: RateLimitConfig,
        limiter: RateLimiter | None = None,
        access_list: AccessListManager | None = None,
        metrics: MetricsCollector | None = None,
    ):
        super().__init__(app)
        self._limiter_ref = limiter
        self._config = config
        self._access_list = access_list or AccessListManager()
        self._metrics = metrics or MetricsCollector()
        self._skip_paths = {"/health", "/docs", "/openapi.json", "/redoc"}

    def _get_limiter(self) -> RateLimiter | None:
        if self._limiter_ref is not None:
            return self._limiter_ref
        try:
            from app.rate_limit.dependencies import get_rate_limiter
            return get_rate_limiter()
        except RuntimeError:
            return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._config.enabled:
            return await call_next(request)

        path = request.url.path
        if path in self._skip_paths:
            return await call_next(request)

        limiter = self._get_limiter()
        if limiter is None:
            return await call_next(request)

        identifier = self._resolve_identifier(request)
        endpoint = self._get_endpoint(request)

        if self._access_list.is_whitelisted(identifier):
            self._metrics.record_whitelist_hit()
            return await call_next(request)

        if self._access_list.is_blacklisted(identifier):
            self._metrics.record_blacklist_hit()
            self._metrics.record_blocked()
            log_request(
                identifier=identifier,
                endpoint=endpoint,
                allowed=False,
                remaining=0,
                limit=0,
                response_time_ms=0,
                block_reason="blacklisted",
                client_ip=self._get_client_ip(request),
            )
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied.", "retry_after": 0},
            )

        start = time.monotonic()
        try:
            result = await limiter.check(identifier, endpoint)
        except Exception as e:
            logger.error("Rate limit check failed: %s — allowing request", e)
            self._metrics.record_redis_error()
            self._metrics.record_storage_fallback()
            return await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000
        self._metrics.record_redis_latency(elapsed_ms)

        if not result.allowed:
            self._metrics.record_blocked()
            log_request(
                identifier=identifier,
                endpoint=endpoint,
                allowed=False,
                remaining=0,
                limit=result.limit,
                response_time_ms=elapsed_ms,
                block_reason="limit_exceeded",
                client_ip=self._get_client_ip(request),
            )
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "Rate limit exceeded.",
                    "retry_after": result.retry_after,
                },
                headers={
                    "RateLimit-Limit": str(result.limit),
                    "RateLimit-Remaining": "0",
                    "RateLimit-Reset": str(int(result.reset_at)),
                    "Retry-After": str(result.retry_after),
                },
            )

        self._metrics.record_allowed()
        log_request(
            identifier=identifier,
            endpoint=endpoint,
            allowed=True,
            remaining=result.remaining,
            limit=result.limit,
            response_time_ms=elapsed_ms,
            client_ip=self._get_client_ip(request),
        )

        response = await call_next(request)
        response.headers["RateLimit-Limit"] = str(result.limit)
        response.headers["RateLimit-Remaining"] = str(result.remaining)
        response.headers["RateLimit-Reset"] = str(int(result.reset_at))
        return response

    def _resolve_identifier(self, request: Request) -> str:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from jose import jwt

                from app.config import settings

                token = auth_header[7:]
                payload = jwt.decode(
                    token,
                    "",
                    algorithms=[settings.algorithm],
                    # Only the `sub` claim is wanted, for the bucket key — the
                    # request is authenticated elsewhere. `key` is positional
                    # even when the signature is not checked, and `verify_aud`
                    # must be off or the aud claim rejects the token here.
                    options={"verify_signature": False, "verify_aud": False},
                )
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except Exception:
                pass

        if self._config.trust_x_forwarded_for:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
                return f"ip:{ip}"

        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"

    def _get_endpoint(self, request: Request) -> str:
        return request.url.path

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
