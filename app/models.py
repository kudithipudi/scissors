"""Database models and queries."""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app.services.supabase_service import SupabaseService


class Game:
    """Game model for database operations."""

    @staticmethod
    def create(game_code: str, best_of: int, host_session_id: str, timeout_minutes: int) -> Dict[str, Any]:
        """Create a new game."""
        client = SupabaseService.get_client()
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)

        data = {
            'game_code': game_code,
            'status': 'waiting',
            'best_of': best_of,
            'host_session_id': host_session_id,
            'expires_at': expires_at.isoformat()
        }

        result = client.table('vs_games').insert(data).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_by_code(game_code: str) -> Optional[Dict[str, Any]]:
        """Get game by game code."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').select('*').eq('game_code', game_code).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_by_id(game_id: str) -> Optional[Dict[str, Any]]:
        """Get game by ID."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').select('*').eq('id', game_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def update(game_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update game by ID."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').update(updates).eq('id', game_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def join_game(game_id: str, guest_session_id: str) -> Optional[Dict[str, Any]]:
        """Join game as guest."""
        updates = {
            'guest_session_id': guest_session_id,
            'status': 'active',
            'started_at': datetime.utcnow().isoformat()
        }
        return Game.update(game_id, updates)

    @staticmethod
    def cancel_game(game_id: str) -> Optional[Dict[str, Any]]:
        """Cancel a game."""
        updates = {
            'status': 'cancelled',
            'completed_at': datetime.utcnow().isoformat()
        }
        return Game.update(game_id, updates)

    @staticmethod
    def complete_game(game_id: str, winner: str) -> Optional[Dict[str, Any]]:
        """Complete a game with winner."""
        updates = {
            'status': 'completed',
            'winner': winner,
            'completed_at': datetime.utcnow().isoformat()
        }
        return Game.update(game_id, updates)

    @staticmethod
    def get_all_active() -> List[Dict[str, Any]]:
        """Get all active games."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').select('*').in_('status', ['waiting', 'active']).execute()
        return result.data if result.data else []

    @staticmethod
    def get_all_with_filters(status: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get games with optional filters."""
        client = SupabaseService.get_client()
        query = client.table('vs_games').select('*')

        if status:
            query = query.eq('status', status)

        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        return result.data if result.data else []

    @staticmethod
    def cleanup_expired() -> int:
        """Mark expired games as cancelled."""
        client = SupabaseService.get_client()
        now = datetime.utcnow().isoformat()

        result = client.table('vs_games').update({
            'status': 'cancelled',
            'completed_at': now
        }).eq('status', 'waiting').lt('expires_at', now).execute()

        return len(result.data) if result.data else 0


class Round:
    """Round model for database operations."""

    @staticmethod
    def create(game_id: str, round_number: int) -> Dict[str, Any]:
        """Create a new round."""
        client = SupabaseService.get_client()
        data = {
            'game_id': game_id,
            'round_number': round_number,
            'host_shakes': 0,
            'guest_shakes': 0
        }
        result = client.table('vs_rounds').insert(data).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_by_game_and_round(game_id: str, round_number: int) -> Optional[Dict[str, Any]]:
        """Get round by game ID and round number."""
        client = SupabaseService.get_client()
        result = client.table('vs_rounds').select('*').eq('game_id', game_id).eq('round_number', round_number).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_all_by_game(game_id: str) -> List[Dict[str, Any]]:
        """Get all rounds for a game."""
        client = SupabaseService.get_client()
        result = client.table('vs_rounds').select('*').eq('game_id', game_id).order('round_number').execute()
        return result.data if result.data else []

    @staticmethod
    def update(round_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update round by ID."""
        client = SupabaseService.get_client()
        result = client.table('vs_rounds').update(updates).eq('id', round_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def update_shakes(round_id: str, player: str, shake_count: int) -> Optional[Dict[str, Any]]:
        """Update shake count for a player."""
        field = f'{player}_shakes'
        updates = {field: shake_count}
        return Round.update(round_id, updates)

    @staticmethod
    def set_choice(round_id: str, player: str, choice: str) -> Optional[Dict[str, Any]]:
        """Set player choice for round."""
        field = f'{player}_choice'
        updates = {field: choice}
        return Round.update(round_id, updates)

    @staticmethod
    def complete_round(round_id: str, winner: str) -> Optional[Dict[str, Any]]:
        """Complete a round with winner."""
        updates = {
            'winner': winner,
            'completed_at': datetime.utcnow().isoformat()
        }
        return Round.update(round_id, updates)


class Statistics:
    """Statistics queries."""

    @staticmethod
    def get_game_count() -> int:
        """Get total game count."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').select('id', count='exact').execute()
        return result.count if hasattr(result, 'count') else 0

    @staticmethod
    def get_active_game_count() -> int:
        """Get active game count."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').select('id', count='exact').in_('status', ['waiting', 'active']).execute()
        return result.count if hasattr(result, 'count') else 0

    @staticmethod
    def get_completed_game_count() -> int:
        """Get completed game count."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').select('id', count='exact').eq('status', 'completed').execute()
        return result.count if hasattr(result, 'count') else 0

    @staticmethod
    def get_game_mode_stats() -> Dict[str, int]:
        """Get statistics by game mode (best_of)."""
        client = SupabaseService.get_client()
        result = client.table('vs_games').select('best_of').eq('status', 'completed').execute()

        stats = {1: 0, 3: 0, 5: 0}
        if result.data:
            for game in result.data:
                best_of = game.get('best_of')
                if best_of in stats:
                    stats[best_of] += 1

        return stats
