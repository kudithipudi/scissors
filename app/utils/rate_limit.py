"""SQLite-backed sliding-window rate limiter for game creation.

Client IPs are read from the X-Forwarded-For / X-Real-IP headers set by
nginx; falls back to the socket peer address when both are absent (e.g.
local dev / tests).
"""
from fastapi import Request

from app.config import settings
from app.db import check_and_record_rate_limit, get_connection

WINDOW_SECONDS = 3600
_ROUTE = "game_create"


def client_ip(request: Request) -> str:
    """Return the client IP, honoring X-Forwarded-For / X-Real-IP from the reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    if request.client is not None:
        return request.client.host
    return "unknown"


async def is_rate_limited(request: Request) -> bool:
    """Check-and-record for the game-creation endpoints.

    Returns True when the client has already used their hourly allowance,
    otherwise records the request and returns False.
    """
    async with get_connection() as conn:
        allowed = await check_and_record_rate_limit(
            conn,
            ip=client_ip(request),
            route=_ROUTE,
            limit=settings.MAX_GAMES_PER_IP_PER_HOUR,
            window_seconds=WINDOW_SECONDS,
        )
    return not allowed


async def reset_rate_limiter() -> None:
    """Clear all recorded rate-limit hits (used by tests)."""
    async with get_connection() as conn:
        await conn.execute("DELETE FROM rate_limit_hits")
