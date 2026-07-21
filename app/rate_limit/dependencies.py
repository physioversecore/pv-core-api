from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.rate_limit.algorithms import RateLimiter
from app.rate_limit.config import RateLimitRule
from app.rate_limit.exceptions import RateLimitExceeded
from app.rate_limit.log import log_request


@dataclass
class RateLimitParams:
    limit: int
    window: int
    identifier: str = "ip"


def rate_limit(
    limit: int,
    window: int,
    identifier: str = "ip",
):
    async def _rate_limit_dependency(
        request: Request,
        limiter: RateLimiter = Depends(get_rate_limiter),
    ):
        client_id = _resolve_identifier(request, identifier)
        endpoint = request.url.path

        start = time.monotonic()
        result = await limiter.check(client_id, endpoint)
        elapsed_ms = (time.monotonic() - start) * 1000

        if not result.allowed:
            log_request(
                identifier=client_id,
                endpoint=endpoint,
                allowed=False,
                remaining=0,
                limit=result.limit,
                response_time_ms=elapsed_ms,
                block_reason="route_limit_exceeded",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
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

        log_request(
            identifier=client_id,
            endpoint=endpoint,
            allowed=True,
            remaining=result.remaining,
            limit=result.limit,
            response_time_ms=elapsed_ms,
        )

        request.state.rate_limit = result

    return _rate_limit_dependency


_rate_limiter_instance: RateLimiter | None = None


def set_rate_limiter(limiter: RateLimiter) -> None:
    global _rate_limiter_instance
    _rate_limiter_instance = limiter


def get_rate_limiter() -> RateLimiter:
    if _rate_limiter_instance is None:
        raise RuntimeError("Rate limiter not initialized. Call set_rate_limiter() first.")
    return _rate_limiter_instance


def _resolve_identifier(request: Request, strategy: str) -> str:
    if strategy == "user":
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from jose import jwt

                token = auth_header[7:]
                payload = jwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except Exception:
                pass
        return f"ip:{_get_client_ip(request)}"

    if strategy == "ip":
        return f"ip:{_get_client_ip(request)}"

    if strategy == "api_key":
        api_key = request.headers.get("x-api-key", "")
        if api_key:
            return f"apikey:{api_key}"
        return f"ip:{_get_client_ip(request)}"

    return f"ip:{_get_client_ip(request)}"


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
