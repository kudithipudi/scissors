"""Test idempotent schema migrations against a pre-existing (old-schema) DB."""
import aiosqlite
import pytest

from app.config import settings
from app.db import init_db


OLD_SCHEMA = """
CREATE TABLE vs_games (
    id TEXT PRIMARY KEY, game_code TEXT UNIQUE NOT NULL, status TEXT NOT NULL,
    best_of INTEGER NOT NULL, host_session_id TEXT NOT NULL, guest_session_id TEXT,
    winner TEXT, created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
    expires_at TEXT NOT NULL
);
CREATE TABLE vs_rounds (
    id TEXT PRIMARY KEY, game_id TEXT NOT NULL, round_number INTEGER NOT NULL,
    host_choice TEXT, guest_choice TEXT, host_shakes INTEGER NOT NULL DEFAULT 0,
    guest_shakes INTEGER NOT NULL DEFAULT 0, winner TEXT,
    created_at TEXT NOT NULL, completed_at TEXT
);
"""


async def test_init_db_adds_forfeited_by_to_existing_table(tmp_path):
    """A DB created before forfeited_by existed must get it added in place —
    CREATE TABLE IF NOT EXISTS is a no-op against an already-created table."""
    db_path = tmp_path / 'legacy.db'
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(OLD_SCHEMA)
        await conn.commit()

    settings.DB_PATH = str(db_path)
    await init_db()

    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("PRAGMA table_info(vs_rounds)")
        columns = {row[1] for row in await cursor.fetchall()}

    assert 'forfeited_by' in columns
