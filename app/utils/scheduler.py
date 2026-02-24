"""Background job scheduler."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit


def cleanup_expired_games():
    """Clean up expired games (run every minute)."""
    from app.models import Game
    try:
        count = Game.cleanup_expired()
        if count > 0:
            print(f"Cleaned up {count} expired games")
    except Exception as e:
        print(f"Error cleaning up games: {e}")


def start_scheduler(app):
    """Start the background scheduler."""
    scheduler = BackgroundScheduler()

    # Add job to cleanup expired games every minute
    scheduler.add_job(
        func=cleanup_expired_games,
        trigger=IntervalTrigger(minutes=1),
        id='cleanup_expired_games',
        name='Cleanup expired games',
        replace_existing=True
    )

    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

    print("Background scheduler started")
