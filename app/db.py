"""SQLite database access module (async, via aiosqlite).

Single place responsible for opening connections, applying the schema, and
providing small helpers (UUIDs, UTC timestamps) used by app/models.py.
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.config import settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


async def init_db() -> None:
    """Create the data directory and apply the schema (idempotent)."""
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.executescript(SCHEMA_PATH.read_text())
        await conn.commit()


@asynccontextmanager
async def get_connection():
    """Yield a connection with row access by column name and FKs enabled."""
    conn = await aiosqlite.connect(settings.DB_PATH, timeout=10)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


async def check_and_record_rate_limit(
    conn: aiosqlite.Connection,
    *,
    ip: str,
    route: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """Sliding-window log check-and-record. Prunes hits for `route` older
    than `window_seconds`, then returns whether (route, ip) is still under
    `limit` within the window -- recording the hit if so."""
    offset = f"-{window_seconds} seconds"
    await conn.execute(
        "DELETE FROM rate_limit_hits WHERE route = ?"
        " AND created_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)",
        (route, offset),
    )
    cursor = await conn.execute(
        "SELECT COUNT(*) FROM rate_limit_hits WHERE route = ? AND ip = ?"
        " AND created_at >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)",
        (route, ip, offset),
    )
    row = await cursor.fetchone()
    if row[0] >= limit:
        return False
    await conn.execute(
        "INSERT INTO rate_limit_hits (ip, route) VALUES (?, ?)", (ip, route)
    )
    return True


def generate_id() -> str:
    """Generate a UUID4 string (replaces Postgres uuid_generate_v4())."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
