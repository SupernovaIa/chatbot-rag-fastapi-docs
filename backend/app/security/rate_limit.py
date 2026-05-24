"""Layer 5 (part 2) · Per-user rate limiting (spec 09).

Keyed by the authenticated ``user_id`` (not IP — several users can share an
egress IP, and the token is the real principal). The chat endpoint is limited
to 30 requests/min per user. On exceed, a layer-5 incident is logged to Phoenix
and the request is rejected with HTTP 429.

Implementation note
-------------------
We use the ``limits`` library (a SlowAPI dependency) directly from a FastAPI
dependency rather than SlowAPI's ``@limiter.limit`` decorator + middleware. The
decorator wraps the endpoint and the middleware is a ``BaseHTTPMiddleware``,
which breaks FastAPI's early security-scheme handling — an unauthenticated
request would 500 (eager adapter construction) instead of returning 401. A
plain dependency runs after authentication and keeps that ordering intact.
"""

from __future__ import annotations

from limits import RateLimitItemPerMinute
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.config import get_settings

# In-process moving-window limiter. Single-worker dev/free-tier deployment, so
# in-memory state is sufficient; swap MemoryStorage for RedisStorage to share
# state across workers in a scaled-out deployment.
_storage = MemoryStorage()
_strategy = MovingWindowRateLimiter(_storage)


def _limit_item() -> RateLimitItemPerMinute:
    settings = get_settings()
    return RateLimitItemPerMinute(getattr(settings, "rate_limit_per_minute", 30))


def check_rate_limit(user_id: str) -> bool:
    """Record a hit for *user_id*; return True if allowed, False if over limit."""
    return _strategy.hit(_limit_item(), "chat", user_id)


def reset() -> None:
    """Clear all rate-limit state (used by tests)."""
    _storage.reset()
