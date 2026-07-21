from __future__ import annotations


class RateLimitExceeded(Exception):
    def __init__(
        self,
        limit: int,
        remaining: int,
        reset_at: float,
        retry_after: int,
        identifier: str = "",
        endpoint: str = "",
    ):
        self.limit = limit
        self.remaining = remaining
        self.reset_at = reset_at
        self.retry_after = retry_after
        self.identifier = identifier
        self.endpoint = endpoint
        super().__init__(
            f"Rate limit exceeded for {identifier} on {endpoint}: "
            f"{limit} reqs/window, retry after {retry_after}s"
        )


class RateLimitStorageError(Exception):
    def __init__(self, message: str = "Rate limit storage unavailable", cause: Exception | None = None):
        self.cause = cause
        super().__init__(message)
