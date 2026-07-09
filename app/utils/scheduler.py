"""Background job scheduler."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("scissors.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def cleanup_expired_games():
    """Clean up expired games (run every minute)."""
    from app.models import Game
    try:
        count = await Game.cleanup_expired()
        if count > 0:
            logger.info("Cleaned up %d expired games", count)
    except Exception as e:
        logger.error("Error cleaning up games: %s", e)


def start_scheduler() -> AsyncIOScheduler:
    """Start the background scheduler. Call stop_scheduler() on shutdown."""
    global _scheduler
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        func=cleanup_expired_games,
        trigger=IntervalTrigger(minutes=1),
        id='cleanup_expired_games',
        name='Cleanup expired games',
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("Background scheduler started")
    return scheduler


def stop_scheduler() -> None:
    """Shut down the background scheduler, if running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
