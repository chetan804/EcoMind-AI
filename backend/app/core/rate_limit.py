"""Per-category rate limiting.

Token buckets keyed by caller identity (user id, device id, or client IP).
The default backend is in-process memory, suitable for a single API node.
Production deployments should run one API node or plug a shared backend —
see docs/adr/0007-background-jobs-and-limits.md for the Redis upgrade path.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Depends, Request

from app.core.config import settings
from app.core.errors import RateLimitError


class TokenBucketLimiter:
    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], tuple[float, float]] = {}
        self._last_sweep = time.monotonic()

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < 300:
            return
        self._buckets = {
            k: v for k, v in self._buckets.items() if v[0] > now - 600
        }
        self._last_sweep = now

    def allow(self, category: str, key: str, limit_per_minute: int) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        self._sweep(now)
        rate = limit_per_minute / 60.0
        capacity = float(limit_per_minute)
        tokens, updated = self._buckets.get((category, key), (capacity, now))
        tokens = min(capacity, tokens + (now - updated) * rate)
        if tokens >= 1.0:
            self._buckets[(category, key)] = (tokens - 1.0, now)
            return True, 0.0
        self._buckets[(category, key)] = (tokens, now)
        return False, (1.0 - tokens) / rate


limiter = TokenBucketLimiter()

_CATEGORY_SETTING = {
    "auth": "rate_limit_auth",
    "write": "rate_limit_write",
    "ai": "rate_limit_ai",
    "upload": "rate_limit_upload",
    "telemetry": "rate_limit_telemetry",
    "read": "rate_limit_read",
}


def rate_limit(category: str):
    """FastAPI dependency factory: `Depends(rate_limit("ai"))`."""

    def _limit(request: Request) -> None:
        user = getattr(request.state, "user_id", None)
        device = getattr(request.state, "device_id", None)
        key = user or device or (request.client.host if request.client else "unknown")
        limit = getattr(settings, _CATEGORY_SETTING.get(category, "rate_limit_read"))
        allowed, retry_after = limiter.allow(category, str(key), limit)
        if not allowed:
            raise RateLimitError(
                "Too many requests in this category. Please retry shortly.",
                details={"retry_after_seconds": round(retry_after, 1), "category": category},
            )

    return _limit


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
