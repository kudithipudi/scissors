"""Tiny in-process pub/sub used to poke WebSocket clients when a game changes.

Why in-process is safe here: gunicorn runs exactly one UvicornWorker for this
app (see gunicorn.conf.py — deliberate, so APScheduler only runs once), so all
requests and all WebSocket connections share this module's state. No Redis, no
persistence, no DB: an event is a transient "something changed, refetch"
notification, and the client always re-reads authoritative state from
/api/game/{code}/state.

Dropping an event is explicitly fine. Each subscriber gets a small bounded
queue; if it is full (a slow or wedged client) we drop the poke rather than
block a request handler. The game page keeps its regular polling running as a
fallback, so a dropped poke costs at most one poll interval of latency.
"""
import asyncio
import logging
from typing import Any, Dict, Set

logger = logging.getLogger("scissors.game_events")

# Small on purpose: these are "refetch now" pokes, not a durable event log.
QUEUE_MAXSIZE = 32

# game_code -> set of subscriber queues
_subscribers: Dict[str, Set["asyncio.Queue[Dict[str, Any]]"]] = {}


def subscribe(game_code: str) -> "asyncio.Queue[Dict[str, Any]]":
    """Register a new subscriber for a game and return its queue."""
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    _subscribers.setdefault(game_code, set()).add(queue)
    return queue


def unsubscribe(game_code: str, queue: "asyncio.Queue[Dict[str, Any]]") -> None:
    """Remove a subscriber queue; safe to call more than once."""
    queues = _subscribers.get(game_code)
    if not queues:
        return
    queues.discard(queue)
    if not queues:
        _subscribers.pop(game_code, None)


def publish(game_code: str, event: Dict[str, Any]) -> int:
    """Fan an event out to every subscriber of a game.

    Synchronous and non-blocking on purpose so callers (game mutations, API
    handlers) can poke listeners without awaiting anything. Returns the number
    of subscribers the event was delivered to.
    """
    queues = _subscribers.get(game_code)
    if not queues:
        return 0

    delivered = 0
    for queue in list(queues):
        try:
            queue.put_nowait(event)
            delivered += 1
        except asyncio.QueueFull:
            # Slow consumer — drop the poke, polling fallback covers it.
            logger.debug("game_events queue full for %s, dropping event", game_code)
        except Exception:  # pragma: no cover - defensive, never break a mutation
            logger.debug("game_events publish failed for %s", game_code, exc_info=True)
    return delivered


def subscriber_count(game_code: str) -> int:
    """Number of live subscribers for a game (diagnostics/tests)."""
    return len(_subscribers.get(game_code, ()))
