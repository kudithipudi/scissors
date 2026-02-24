"""Test game service logic."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.game_service import GameService


class TestCreateGame:
    """Test game creation."""

    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    def test_create_game_best_of_three(self, mock_round, mock_game, app):
        """Test creating a best of 3 game."""
        with app.app_context():
            # Mock successful game creation
            mock_game.get_by_code.return_value = None  # Code is unique
            mock_game.create.return_value = {
                'id': 'game-id',
                'game_code': 'ABC123',
                'status': 'waiting',
                'best_of': 3
            }
            mock_round.create.return_value = {'id': 'round-id'}

            game, error = GameService.create_game(3, 'host-session-id')

            assert error is None
            assert game is not None
            assert game['best_of'] == 3
            mock_round.create.assert_called_once()

    @patch('app.services.game_service.Game')
    def test_create_game_invalid_best_of(self, mock_game):
        """Test creating game with invalid best_of."""
        game, error = GameService.create_game(7, 'host-session-id')

        assert game is None
        assert error == "Invalid game mode. Must be best of 1, 3, or 5."

    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.generate_game_code')
    def test_create_game_generates_unique_code(self, mock_generate, mock_game, app):
        """Test that game code generation retries until unique."""
        with app.app_context():
            # First code exists, second is unique
            mock_generate.side_effect = ['EXISTS', 'UNIQUE']
            mock_game.get_by_code.side_effect = [
                {'game_code': 'EXISTS'},  # First attempt exists
                None  # Second attempt is unique
            ]
            mock_game.create.return_value = {'id': 'game-id', 'game_code': 'UNIQUE'}

            game, error = GameService.create_game(1, 'host-session-id')

            assert game is not None
            assert mock_generate.call_count == 2


class TestJoinGame:
    """Test joining games."""

    @patch('app.services.game_service.Game')
    def test_join_waiting_game(self, mock_game):
        """Test joining a waiting game."""
        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'waiting',
            'host_session_id': 'host-id',
            'guest_session_id': None
        }
        mock_game.join_game.return_value = {
            'id': 'game-id',
            'status': 'active'
        }

        game, error = GameService.join_game('ABC123', 'guest-id')

        assert error is None
        assert game['status'] == 'active'

    @patch('app.services.game_service.Game')
    def test_join_nonexistent_game(self, mock_game):
        """Test joining non-existent game."""
        mock_game.get_by_code.return_value = None

        game, error = GameService.join_game('FAKE', 'guest-id')

        assert game is None
        assert error == "Game not found."

    @patch('app.services.game_service.Game')
    def test_join_active_game(self, mock_game):
        """Test joining already active game."""
        mock_game.get_by_code.return_value = {
            'status': 'active',
            'guest_session_id': 'other-guest'
        }

        game, error = GameService.join_game('ABC123', 'guest-id')

        assert game is None
        assert error == "Game is active. Cannot join."

    @patch('app.services.game_service.Game')
    def test_host_cannot_join_as_guest(self, mock_game):
        """Test host cannot join their own game as guest."""
        mock_game.get_by_code.return_value = {
            'status': 'waiting',
            'host_session_id': 'same-id'
        }

        game, error = GameService.join_game('ABC123', 'same-id')

        assert game is None
        assert error == "You are the host. Cannot join as guest."


class TestSubmitChoice:
    """Test submitting player choices."""

    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    def test_submit_choice_first_player(self, mock_round, mock_game):
        """Test first player submitting choice."""
        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'active',
            'best_of': 3
        }
        mock_round.get_all_by_game.return_value = [
            {'id': 'round-id', 'round_number': 1}
        ]
        mock_round.get_by_game_and_round.return_value = {
            'id': 'round-id',
            'host_choice': 'rock',
            'guest_choice': None
        }

        result, error = GameService.submit_choice('ABC123', 'host', 'rock')

        assert error is None
        assert result is not None
        mock_round.set_choice.assert_called_once()

    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    def test_submit_choice_both_players_determines_winner(self, mock_round, mock_game):
        """Test when both players choose, winner is determined."""
        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'active',
            'best_of': 3
        }
        mock_round.get_all_by_game.return_value = [
            {'id': 'round-id', 'round_number': 1}
        ]
        mock_round.get_by_game_and_round.return_value = {
            'id': 'round-id',
            'round_number': 1,
            'host_choice': 'rock',
            'guest_choice': 'scissors'
        }

        result, error = GameService.submit_choice('ABC123', 'guest', 'scissors')

        assert error is None
        mock_round.complete_round.assert_called_once_with('round-id', 'host')

    @patch('app.services.game_service.Game')
    def test_submit_invalid_choice(self, mock_game):
        """Test submitting invalid choice."""
        result, error = GameService.submit_choice('ABC123', 'host', 'invalid')

        assert result is None
        assert error == "Invalid choice."


class TestCancelGame:
    """Test game cancellation."""

    @patch('app.services.game_service.Game')
    def test_host_can_cancel(self, mock_game):
        """Test host can cancel their game."""
        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'waiting',
            'host_session_id': 'host-id'
        }

        success, error = GameService.cancel_game('ABC123', 'host-id')

        assert success is True
        assert error is None
        mock_game.cancel_game.assert_called_once()

    @patch('app.services.game_service.Game')
    def test_guest_cannot_cancel(self, mock_game):
        """Test guest cannot cancel game."""
        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'waiting',
            'host_session_id': 'host-id'
        }

        success, error = GameService.cancel_game('ABC123', 'guest-id')

        assert success is False
        assert error == "Only the host can cancel the game."

    @patch('app.services.game_service.Game')
    def test_cannot_cancel_completed_game(self, mock_game):
        """Test cannot cancel completed game."""
        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'completed',
            'host_session_id': 'host-id'
        }

        success, error = GameService.cancel_game('ABC123', 'host-id')

        assert success is False
        assert error == "Cannot cancel completed game."
