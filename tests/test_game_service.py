"""Test game service logic."""
import pytest
from unittest.mock import patch, AsyncMock
from app.services.game_service import GameService, COMPUTER_PLAYER_ID


class TestCreateGame:
    """Test game creation."""

    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    async def test_create_game_best_of_three(self, mock_round, mock_game):
        """Test creating a best of 3 game."""
        # Mock successful game creation
        mock_game.get_by_code = AsyncMock(return_value=None)  # Code is unique
        mock_game.create = AsyncMock(return_value={
            'id': 'game-id',
            'game_code': 'ABC123',
            'status': 'waiting',
            'best_of': 3
        })
        mock_round.create = AsyncMock(return_value={'id': 'round-id'})

        game, error = await GameService.create_game(3, 'host-session-id')

        assert error is None
        assert game is not None
        assert game['best_of'] == 3
        mock_round.create.assert_called_once()

    @patch('app.services.game_service.Game')
    async def test_create_game_invalid_best_of(self, mock_game):
        """Test creating game with invalid best_of."""
        game, error = await GameService.create_game(7, 'host-session-id')

        assert game is None
        assert error == "Invalid game mode. Must be best of 1, 3, or 5."

    @patch('app.services.game_service.Round')
    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.generate_game_code')
    async def test_create_game_generates_unique_code(self, mock_generate, mock_game, mock_round):
        """Test that game code generation retries until unique."""
        # First code exists, second is unique
        mock_generate.side_effect = ['EXISTS', 'UNIQUE']
        mock_game.get_by_code = AsyncMock(side_effect=[
            {'game_code': 'EXISTS'},  # First attempt exists
            None  # Second attempt is unique
        ])
        mock_game.create = AsyncMock(return_value={'id': 'game-id', 'game_code': 'UNIQUE'})
        mock_round.create = AsyncMock(return_value={'id': 'round-id'})

        game, error = await GameService.create_game(1, 'host-session-id')

        assert game is not None
        assert mock_generate.call_count == 2

    @patch('app.services.game_service.Round')
    @patch('app.services.game_service.Game')
    async def test_create_game_vs_computer_starts_active(self, mock_game, mock_round):
        """A vs-computer game is immediately joined by the COMPUTER sentinel and goes active."""
        mock_game.get_by_code = AsyncMock(return_value=None)
        mock_game.create = AsyncMock(return_value={
            'id': 'game-id', 'game_code': 'ABC123', 'status': 'waiting', 'best_of': 3
        })
        mock_game.join_game = AsyncMock(return_value={
            'id': 'game-id', 'game_code': 'ABC123', 'status': 'active',
            'guest_session_id': COMPUTER_PLAYER_ID,
        })
        mock_round.create = AsyncMock(return_value={'id': 'round-id'})

        game, error = await GameService.create_game(3, 'host-session-id', vs_computer=True)

        assert error is None
        assert game['status'] == 'active'
        assert game['guest_session_id'] == COMPUTER_PLAYER_ID
        mock_game.join_game.assert_called_once_with('game-id', COMPUTER_PLAYER_ID)


class TestJoinGame:
    """Test joining games."""

    @patch('app.services.game_service.Game')
    async def test_join_waiting_game(self, mock_game):
        """Test joining a waiting game."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id',
            'status': 'waiting',
            'host_session_id': 'host-id',
            'guest_session_id': None
        })
        mock_game.join_game = AsyncMock(return_value={
            'id': 'game-id',
            'status': 'active'
        })

        game, error = await GameService.join_game('ABC123', 'guest-id')

        assert error is None
        assert game['status'] == 'active'

    @patch('app.services.game_service.Game')
    async def test_join_nonexistent_game(self, mock_game):
        """Test joining non-existent game."""
        mock_game.get_by_code = AsyncMock(return_value=None)

        game, error = await GameService.join_game('FAKE', 'guest-id')

        assert game is None
        assert error == "Game not found."

    @patch('app.services.game_service.Game')
    async def test_join_active_game(self, mock_game):
        """Test joining already active game."""
        mock_game.get_by_code = AsyncMock(return_value={
            'status': 'active',
            'guest_session_id': 'other-guest'
        })

        game, error = await GameService.join_game('ABC123', 'guest-id')

        assert game is None
        assert error == "Game is active. Cannot join."

    @patch('app.services.game_service.Game')
    async def test_host_cannot_join_as_guest(self, mock_game):
        """Test host cannot join their own game as guest."""
        mock_game.get_by_code = AsyncMock(return_value={
            'status': 'waiting',
            'host_session_id': 'same-id'
        })

        game, error = await GameService.join_game('ABC123', 'same-id')

        assert game is None
        assert error == "You are the host. Cannot join as guest."


class TestSubmitChoice:
    """Test submitting player choices."""

    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    async def test_submit_choice_first_player(self, mock_round, mock_game):
        """Test first player submitting choice."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id',
            'status': 'active',
            'best_of': 3
        })
        mock_round.get_all_by_game = AsyncMock(return_value=[
            {'id': 'round-id', 'round_number': 1}
        ])
        mock_round.get_by_game_and_round = AsyncMock(return_value={
            'id': 'round-id',
            'host_choice': 'rock',
            'guest_choice': None
        })
        mock_round.set_choice = AsyncMock()

        result, error = await GameService.submit_choice('ABC123', 'host', 'rock')

        assert error is None
        assert result is not None
        mock_round.set_choice.assert_called_once()

    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    async def test_submit_choice_both_players_determines_winner(self, mock_round, mock_game):
        """Test when both players choose, winner is determined."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id',
            'status': 'active',
            'best_of': 3
        })
        mock_round.get_all_by_game = AsyncMock(return_value=[
            {'id': 'round-id', 'round_number': 1}
        ])
        mock_round.get_by_game_and_round = AsyncMock(return_value={
            'id': 'round-id',
            'round_number': 1,
            'host_choice': 'rock',
            'guest_choice': 'scissors'
        })
        mock_round.set_choice = AsyncMock()
        mock_round.complete_round = AsyncMock()

        result, error = await GameService.submit_choice('ABC123', 'guest', 'scissors')

        assert error is None
        mock_round.complete_round.assert_called_once_with('round-id', 'host')

    @patch('app.services.game_service.Game')
    async def test_submit_invalid_choice(self, mock_game):
        """Test submitting invalid choice."""
        result, error = await GameService.submit_choice('ABC123', 'host', 'invalid')

        assert result is None
        assert error == "Invalid choice."

    @patch('app.services.game_service.asyncio.sleep', new_callable=AsyncMock)
    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    async def test_submit_choice_vs_computer_auto_plays_guest(self, mock_round, mock_game, mock_sleep):
        """Host's move against a computer opponent triggers an automatic guest move."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id', 'status': 'active', 'best_of': 3,
            'guest_session_id': COMPUTER_PLAYER_ID,
        })
        mock_round.get_all_by_game = AsyncMock(return_value=[
            {'id': 'round-id', 'round_number': 1}
        ])
        mock_round.get_by_game_and_round = AsyncMock(return_value={
            'id': 'round-id', 'round_number': 1, 'host_choice': 'rock', 'guest_choice': 'scissors'
        })
        mock_round.set_choice = AsyncMock()
        mock_round.complete_round = AsyncMock()

        result, error = await GameService.submit_choice('ABC123', 'host', 'rock')

        assert error is None
        assert mock_round.set_choice.call_count == 2
        calls = mock_round.set_choice.call_args_list
        assert calls[0].args == ('round-id', 'host', 'rock')
        assert calls[1].args[0] == 'round-id'
        assert calls[1].args[1] == 'guest'
        assert calls[1].args[2] in ('rock', 'paper', 'scissors')
        mock_sleep.assert_awaited_once()


class TestGetGameState:
    """Test game state reporting."""

    @patch('app.services.game_service.Round')
    @patch('app.services.game_service.Game')
    async def test_current_round_counts_only_decisive_rounds(self, mock_game, mock_round):
        """Tied rounds replay the same match round, so ties shouldn't inflate
        current_round past best_of."""
        mock_game.get_by_code = AsyncMock(return_value={'id': 'game-id', 'best_of': 3})
        # Round 1 was won by host, then round 1 was replayed twice more
        # after ties before round 2 (a fresh decisive round) began — 4 DB
        # rows total for what a player would call "round 2".
        mock_round.get_all_by_game = AsyncMock(return_value=[
            {'round_number': 1, 'winner': 'host'},
            {'round_number': 2, 'winner': 'tie'},
            {'round_number': 3, 'winner': 'tie'},
            {'round_number': 4, 'winner': None},
        ])

        state = await GameService.get_game_state('ABC123')

        assert state['current_round'] == 2

    @patch('app.services.game_service.Round')
    @patch('app.services.game_service.Game')
    async def test_current_round_never_exceeds_best_of(self, mock_game, mock_round):
        """Even with a decisive round count at the cap, current_round stays <= best_of."""
        mock_game.get_by_code = AsyncMock(return_value={'id': 'game-id', 'best_of': 1})
        mock_round.get_all_by_game = AsyncMock(return_value=[
            {'round_number': 1, 'winner': 'host'},
        ])

        state = await GameService.get_game_state('ABC123')

        assert state['current_round'] == 1


class TestCancelGame:
    """Test game cancellation."""

    @patch('app.services.game_service.Game')
    async def test_host_can_cancel(self, mock_game):
        """Test host can cancel their game."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id',
            'status': 'waiting',
            'host_session_id': 'host-id'
        })
        mock_game.cancel_game = AsyncMock()

        success, error = await GameService.cancel_game('ABC123', 'host-id')

        assert success is True
        assert error is None
        mock_game.cancel_game.assert_called_once()

    @patch('app.services.game_service.Game')
    async def test_guest_cannot_cancel(self, mock_game):
        """Test guest cannot cancel game."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id',
            'status': 'waiting',
            'host_session_id': 'host-id'
        })

        success, error = await GameService.cancel_game('ABC123', 'guest-id')

        assert success is False
        assert error == "Only the host can cancel the game."

    @patch('app.services.game_service.Game')
    async def test_cannot_cancel_completed_game(self, mock_game):
        """Test cannot cancel completed game."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id',
            'status': 'completed',
            'host_session_id': 'host-id'
        })

        success, error = await GameService.cancel_game('ABC123', 'host-id')

        assert success is False
        assert error == "Cannot cancel completed game."
