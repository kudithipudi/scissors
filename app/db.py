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
    conn = await aiosqlite.connect(settings.DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


def generate_id() -> str:
    """Generate a UUID4 string (replaces Postgres uuid_generate_v4())."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
