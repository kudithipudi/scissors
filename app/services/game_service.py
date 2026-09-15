"""Game service with core game logic."""
import asyncio
import random
from typing import Optional, Dict, Any, Tuple

from app.config import settings
from app.models import Game, Round
from app.services import game_events
from app.utils.helpers import (
    generate_game_code,
    is_valid_choice,
    determine_winner,
    calculate_game_winner,
    random_choice,
)

# Sentinel guest_session_id for a solo game against the computer. No real
# session ever equals this, so the computer never matches as a player role
# for an incoming request - only the server itself plays this "guest".
COMPUTER_PLAYER_ID = "COMPUTER"

# How long the computer "thinks" before its move lands, so a solo round
# doesn't resolve instantly.
_COMPUTER_MOVE_DELAY_RANGE = (0.4, 0.9)


class GameService:
    """Service class for game operations."""

    @staticmethod
    async def create_game(
        best_of: int, host_session_id: str, vs_computer: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Create a new game.

        Returns:
            Tuple of (game_data, error_message)
        """
        # Validate best_of
        if best_of not in [1, 3, 5]:
            return None, "Invalid game mode. Must be best of 1, 3, or 5."

        # Generate unique game code
        max_attempts = 10
        for _ in range(max_attempts):
            game_code = generate_game_code()
            existing = await Game.get_by_code(game_code)
            if not existing:
                break
        else:
            return None, "Failed to generate unique game code. Please try again."

        # Create game in database
        timeout_minutes = settings.GAME_TIMEOUT_MINUTES
        game = await Game.create(game_code, best_of, host_session_id, timeout_minutes)

        if not game:
            return None, "Failed to create game. Please try again."

        # Create first round
        await Round.create(game['id'], 1)

        if vs_computer:
            # Skip the waiting room entirely: the computer "joins" immediately.
            game = await Game.join_game(game['id'], COMPUTER_PLAYER_ID)

        return game, None

    @staticmethod
    async def join_game(game_code: str, guest_session_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Join an existing game as guest.

        Returns:
            Tuple of (game_data, error_message)
        """
        # Get game
        game = await Game.get_by_code(game_code)
        if not game:
            return None, "Game not found."

        # Check game status
        if game['status'] != 'waiting':
            return None, f"Game is {game['status']}. Cannot join."

        # Check if game is full
        if game.get('guest_session_id'):
            return None, "Game is full."

        # Check if user is the host
        if game['host_session_id'] == guest_session_id:
            return None, "You are the host. Cannot join as guest."

        # Join game
        updated_game = await Game.join_game(game['id'], guest_session_id)

        if not updated_game:
            return None, "Failed to join game."

        # Poke any connected WebSocket clients (host is waiting on this).
        game_events.publish(game_code, {"type": "state"})

        return updated_game, None

    @staticmethod
    async def cancel_game(game_code: str, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        Cancel a game.

        Returns:
            Tuple of (success, error_message)
        """
        game = await Game.get_by_code(game_code)
        if not game:
            return False, "Game not found."

        # Only host can cancel
        if game['host_session_id'] != session_id:
            return False, "Only the host can cancel the game."

        # Can only cancel waiting or active games
        if game['status'] not in ['waiting', 'active']:
            return False, f"Cannot cancel {game['status']} game."

        await Game.cancel_game(game['id'])
        game_events.publish(game_code, {"type": "state"})
        return True, None

    @staticmethod
    async def get_game_state(game_code: str) -> Optional[Dict[str, Any]]:
        """Get full game state including rounds."""
        game = await Game.get_by_code(game_code)
        if not game:
            return None

        rounds = await Round.get_all_by_game(game['id'])

        return {
            'game': game,
            'rounds': rounds,
            'current_round': len(rounds)
        }

    @staticmethod
    async def record_shake(game_code: str, player: str, shake_count: int) -> Tuple[bool, Optional[str]]:
        """
        Record shake count for a player.

        Returns:
            Tuple of (success, error_message)
        """
        game = await Game.get_by_code(game_code)
        if not game or game['status'] != 'active':
            return False, "Invalid game state."

        # Get current round
        rounds = await Round.get_all_by_game(game['id'])
        if not rounds:
            return False, "No active round."

        current_round = rounds[-1]

        # Validate shake count
        if shake_count < 0 or shake_count > settings.REQUIRED_SHAKES:
            return False, "Invalid shake count."

        # Update shake count
        await Round.update_shakes(current_round['id'], player, shake_count)
        return True, None

    @staticmethod
    async def submit_choice(game_code: str, player: str, choice: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Submit player choice for current round.

        Returns:
            Tuple of (round_result, error_message)
        """
        # Validate choice
        if not is_valid_choice(choice):
            return None, "Invalid choice."

        game = await Game.get_by_code(game_code)
        if not game or game['status'] != 'active':
            return None, "Invalid game state."

        # Get current round
        rounds = await Round.get_all_by_game(game['id'])
        if not rounds:
            return None, "No active round."

        current_round = rounds[-1]

        # Guard: if this round is already completed, don't process again
        if current_round.get('winner') is not None or current_round.get('completed_at'):
            return current_round, None

        # Set choice
        await Round.set_choice(current_round['id'], player, choice)

        # Solo mode: the human just moved, so make the computer's move too.
        if player == 'host' and game.get('guest_session_id') == COMPUTER_PLAYER_ID:
            await GameService._play_computer_turn(current_round['id'])

        # Check if both players have chosen
        updated_round = await Round.get_by_game_and_round(game['id'], current_round['round_number'])
        host_choice = updated_round.get('host_choice')
        guest_choice = updated_round.get('guest_choice')

        if host_choice and guest_choice:
            # Guard: re-check if round was already completed by concurrent request
            if updated_round.get('winner') is not None or updated_round.get('completed_at'):
                return updated_round, None

            # Determine round winner
            winner = determine_winner(host_choice, guest_choice)
            await Round.complete_round(updated_round['id'], winner)

            # Re-fetch game to check if it was already completed by concurrent request
            game = await Game.get_by_code(game_code)
            if game['status'] == 'completed':
                game_events.publish(game_code, {"type": "state"})
                return updated_round, None

            # Check if game is complete
            all_rounds = await Round.get_all_by_game(game['id'])
            game_winner = calculate_game_winner(all_rounds, game['best_of'])

            if game_winner:
                # Game complete
                await Game.complete_game(game['id'], game_winner)
            else:
                # Only create next round if an incomplete one doesn't already exist
                has_pending_round = any(
                    r.get('winner') is None and not r.get('completed_at')
                    for r in all_rounds
                )
                if not has_pending_round:
                    next_round_number = max(r['round_number'] for r in all_rounds) + 1
                    await Round.create(game['id'], next_round_number)

            # Both choices are in and every write for this round is durable:
            # poke listeners so the reveal happens immediately instead of on
            # the next poll tick. Published last so a client that refetches on
            # this event always sees the settled game status.
            game_events.publish(game_code, {"type": "state"})

            return updated_round, None

        return updated_round, None

    @staticmethod
    async def _play_computer_turn(round_id: str) -> None:
        """Make the computer opponent's move for the given round."""
        await asyncio.sleep(random.uniform(*_COMPUTER_MOVE_DELAY_RANGE))
        await Round.set_choice(round_id, 'guest', random_choice())

    @staticmethod
    def is_player_in_game(game: Dict[str, Any], session_id: str) -> bool:
        """Check if session ID is a player in the game."""
        return session_id in [game.get('host_session_id'), game.get('guest_session_id')]

    @staticmethod
    def get_player_role(game: Dict[str, Any], session_id: str) -> Optional[str]:
        """Get player role (host or guest)."""
        if game.get('host_session_id') == session_id:
            return 'host'
        elif game.get('guest_session_id') == session_id:
            return 'guest'
        return None
