"""Database models and queries (SQLite, async via aiosqlite)."""
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.db import get_connection, generate_id, now_iso

_GAME_COLUMNS = {
    'game_code', 'status', 'best_of', 'host_session_id', 'guest_session_id',
    'winner', 'created_at', 'started_at', 'completed_at', 'expires_at',
}
_ROUND_COLUMNS = {
    'game_id', 'round_number', 'host_choice', 'guest_choice', 'host_shakes',
    'guest_shakes', 'winner', 'created_at', 'completed_at',
}


def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


class Game:
    """Game model for database operations."""

    @staticmethod
    async def create(game_code: str, best_of: int, host_session_id: str, timeout_minutes: int) -> Dict[str, Any]:
        """Create a new game."""
        game_id = generate_id()
        created_at = now_iso()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)).isoformat()

        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO vs_games
                    (id, game_code, status, best_of, host_session_id, guest_session_id,
                     winner, created_at, started_at, completed_at, expires_at)
                VALUES (?, ?, 'waiting', ?, ?, NULL, NULL, ?, NULL, NULL, ?)
                """,
                (game_id, game_code, best_of, host_session_id, created_at, expires_at),
            )

        return await Game.get_by_id(game_id)

    @staticmethod
    async def get_by_code(game_code: str) -> Optional[Dict[str, Any]]:
        """Get game by game code."""
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM vs_games WHERE game_code = ?", (game_code,))
            row = await cursor.fetchone()
        return _row_to_dict(row)

    @staticmethod
    async def get_by_id(game_id: str) -> Optional[Dict[str, Any]]:
        """Get game by ID."""
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM vs_games WHERE id = ?", (game_id,))
            row = await cursor.fetchone()
        return _row_to_dict(row)

    @staticmethod
    async def update(game_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update game by ID."""
        updates = {k: v for k, v in updates.items() if k in _GAME_COLUMNS}
        if not updates:
            return await Game.get_by_id(game_id)

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        params = list(updates.values()) + [game_id]

        async with get_connection() as conn:
            await conn.execute(f"UPDATE vs_games SET {set_clause} WHERE id = ?", params)

        return await Game.get_by_id(game_id)

    @staticmethod
    async def join_game(game_id: str, guest_session_id: str) -> Optional[Dict[str, Any]]:
        """Join game as guest."""
        updates = {
            'guest_session_id': guest_session_id,
            'status': 'active',
            'started_at': now_iso(),
        }
        return await Game.update(game_id, updates)

    @staticmethod
    async def cancel_game(game_id: str) -> Optional[Dict[str, Any]]:
        """Cancel a game."""
        updates = {
            'status': 'cancelled',
            'completed_at': now_iso(),
        }
        return await Game.update(game_id, updates)

    @staticmethod
    async def complete_game(game_id: str, winner: str) -> Optional[Dict[str, Any]]:
        """Complete a game with winner."""
        updates = {
            'status': 'completed',
            'winner': winner,
            'completed_at': now_iso(),
        }
        return await Game.update(game_id, updates)

    @staticmethod
    async def get_all_active() -> List[Dict[str, Any]]:
        """Get all active games."""
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM vs_games WHERE status IN ('waiting', 'active')")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_all_with_filters(status: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get games with optional filters."""
        query = "SELECT * FROM vs_games"
        params: List[Any] = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def cleanup_expired() -> int:
        """Mark expired games as cancelled."""
        now = now_iso()
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE vs_games
                SET status = 'cancelled', completed_at = ?
                WHERE status = 'waiting' AND expires_at < ?
                """,
                (now, now),
            )
            return cursor.rowcount


class Round:
    """Round model for database operations."""

    @staticmethod
    async def create(game_id: str, round_number: int) -> Dict[str, Any]:
        """Create a new round."""
        round_id = generate_id()
        created_at = now_iso()

        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO vs_rounds
                    (id, game_id, round_number, host_choice, guest_choice,
                     host_shakes, guest_shakes, winner, created_at, completed_at)
                VALUES (?, ?, ?, NULL, NULL, 0, 0, NULL, ?, NULL)
                """,
                (round_id, game_id, round_number, created_at),
            )

        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM vs_rounds WHERE id = ?", (round_id,))
            row = await cursor.fetchone()
        return _row_to_dict(row)

    @staticmethod
    async def get_by_game_and_round(game_id: str, round_number: int) -> Optional[Dict[str, Any]]:
        """Get round by game ID and round number."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM vs_rounds WHERE game_id = ? AND round_number = ?",
                (game_id, round_number),
            )
            row = await cursor.fetchone()
        return _row_to_dict(row)

    @staticmethod
    async def get_all_by_game(game_id: str) -> List[Dict[str, Any]]:
        """Get all rounds for a game."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM vs_rounds WHERE game_id = ? ORDER BY round_number",
                (game_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def update(round_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update round by ID."""
        updates = {k: v for k, v in updates.items() if k in _ROUND_COLUMNS}
        if updates:
            set_clause = ", ".join(f"{col} = ?" for col in updates)
            params = list(updates.values()) + [round_id]
            async with get_connection() as conn:
                await conn.execute(f"UPDATE vs_rounds SET {set_clause} WHERE id = ?", params)

        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM vs_rounds WHERE id = ?", (round_id,))
            row = await cursor.fetchone()
        return _row_to_dict(row)

    @staticmethod
    async def update_shakes(round_id: str, player: str, shake_count: int) -> Optional[Dict[str, Any]]:
        """Update shake count for a player."""
        if player not in ('host', 'guest'):
            raise ValueError("player must be 'host' or 'guest'")
        field = f'{player}_shakes'
        return await Round.update(round_id, {field: shake_count})

    @staticmethod
    async def set_choice(round_id: str, player: str, choice: str) -> Optional[Dict[str, Any]]:
        """Set player choice for round."""
        if player not in ('host', 'guest'):
            raise ValueError("player must be 'host' or 'guest'")
        field = f'{player}_choice'
        return await Round.update(round_id, {field: choice})

    @staticmethod
    async def complete_round(round_id: str, winner: str) -> Optional[Dict[str, Any]]:
        """Complete a round with winner."""
        updates = {
            'winner': winner,
            'completed_at': now_iso(),
        }
        return await Round.update(round_id, updates)


class Statistics:
    """Statistics queries."""

    @staticmethod
    async def get_game_count() -> int:
        """Get total game count."""
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) AS c FROM vs_games")
            row = await cursor.fetchone()
        return row['c'] if row else 0

    @staticmethod
    async def get_active_game_count() -> int:
        """Get active game count."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS c FROM vs_games WHERE status IN ('waiting', 'active')"
            )
            row = await cursor.fetchone()
        return row['c'] if row else 0

    @staticmethod
    async def get_completed_game_count() -> int:
        """Get completed game count."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS c FROM vs_games WHERE status = 'completed'"
            )
            row = await cursor.fetchone()
        return row['c'] if row else 0

    @staticmethod
    async def get_game_mode_stats() -> Dict[int, int]:
        """Get statistics by game mode (best_of)."""
        stats = {1: 0, 3: 0, 5: 0}
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT best_of, COUNT(*) AS c FROM vs_games WHERE status = 'completed' GROUP BY best_of"
            )
            rows = await cursor.fetchall()
        for row in rows:
            if row['best_of'] in stats:
                stats[row['best_of']] = row['c']
        return stats
