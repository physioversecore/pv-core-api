from __future__ import annotations

import logging
import time

logger = logging.getLogger("rate_limit")


def log_request(
    identifier: str,
    endpoint: str,
    allowed: bool,
    remaining: int,
    limit: int,
    response_time_ms: float,
    block_reason: str = "",
    client_ip: str = "",
) -> None:
    status = "ALLOWED" if allowed else "BLOCKED"
    extra_parts = [
        f"identifier={identifier}",
        f"endpoint={endpoint}",
        f"status={status}",
        f"remaining={remaining}/{limit}",
        f"response_time={response_time_ms:.2f}ms",
    ]
    if client_ip:
        extra_parts.append(f"client_ip={client_ip}")
    if block_reason:
        extra_parts.append(f"block_reason={block_reason}")

    message = "Rate limit check " + " ".join(extra_parts)

    if allowed:
        logger.info(message)
    else:
        logger.warning(message)


def log_startup(backend: str, redis_url: str = "", enabled: bool = True) -> None:
    if enabled:
        logger.info("Rate limiting enabled (backend=%s, redis=%s)", backend, redis_url or "N/A")
    else:
        logger.info("Rate limiting disabled")


def log_storage_error(error: Exception, context: str = "") -> None:
    logger.error("Rate limit storage error%s: %s", f" ({context})" if context else "", error)
