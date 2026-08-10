"""In-memory sliding-window rate limiter for game creation.

The app runs a single Gunicorn worker (see gunicorn.conf.py), so an
in-memory store is sufficient. Client IPs are read from the X-Forwarded-For
header set by nginx; the first (client) entry is used. Falls back to the
socket peer address when the header is absent (e.g. local dev / tests).
"""
import time
from collections import defaultdict, deque

from fastapi import Request

from app.config import settings

_requests: dict[str, deque] = defaultdict(deque)

WINDOW_SECONDS = 3600


def client_ip(request: Request) -> str:
    """Return the client IP, honoring X-Forwarded-For from the reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def is_rate_limited(request: Request) -> bool:
    """Check-and-record for the game-creation endpoints.

    Returns True when the client has already used their hourly allowance,
    otherwise records the request and returns False.
    """
    now = time.time()
    key = client_ip(request)
    window = _requests[key]

    # Drop entries that have fallen out of the window.
    while window and now - window[0] >= WINDOW_SECONDS:
        window.popleft()

    if len(window) >= settings.MAX_GAMES_PER_IP_PER_HOUR:
        return True

    window.append(now)
    return False


def reset_rate_limiter() -> None:
    """Clear all recorded requests (used by tests)."""
    _requests.clear()
