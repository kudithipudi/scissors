"""Test API endpoints."""
import pytest
from unittest.mock import patch
import json


class TestStatsAPI:
    """Test statistics API."""

    @patch('app.routes.api.Statistics')
    def test_get_stats(self, mock_stats, client):
        """Test getting public statistics."""
        mock_stats.get_active_game_count.return_value = 5
        mock_stats.get_game_count.return_value = 100

        response = client.get('/api/stats')

        assert response.status_code == 200
        data = response.get_json()
        assert data['active_games'] == 5
        assert data['total_games'] == 100


class TestGameStateAPI:
    """Test game state API."""

    @patch('app.routes.api.GameService')
    def test_get_game_state(self, mock_service, client):
        """Test getting game state."""
        mock_service.get_game_state.return_value = {
            'game': {'id': 'game-id', 'status': 'active'},
            'rounds': [],
            'current_round': 1
        }

        response = client.get('/api/game/ABC123/state')

        assert response.status_code == 200
        data = response.get_json()
        assert data['game']['status'] == 'active'

    @patch('app.routes.api.GameService')
    def test_get_game_state_not_found(self, mock_service, client):
        """Test getting state of non-existent game."""
        mock_service.get_game_state.return_value = None

        response = client.get('/api/game/FAKE/state')

        assert response.status_code == 404


class TestShakeAPI:
    """Test shake recording API."""

    @patch('app.routes.api.Game')
    @patch('app.routes.api.GameService')
    def test_record_shake(self, mock_service, mock_game, client):
        """Test recording shake count."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'active',
            'host_session_id': 'host-id'
        }
        mock_service.get_player_role.return_value = 'host'
        mock_service.record_shake.return_value = (True, None)

        response = client.post(
            '/api/game/ABC123/shake',
            json={'shake_count': 2}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['shake_count'] == 2

    def test_record_shake_no_session(self, client):
        """Test recording shake without session."""
        response = client.post(
            '/api/game/ABC123/shake',
            json={'shake_count': 2}
        )

        assert response.status_code == 401


class TestChoiceAPI:
    """Test choice submission API."""

    @patch('app.routes.api.Game')
    @patch('app.routes.api.GameService')
    def test_submit_choice(self, mock_service, mock_game, client):
        """Test submitting a choice."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'active',
            'host_session_id': 'host-id'
        }
        mock_service.get_player_role.return_value = 'host'
        mock_service.submit_choice.return_value = (
            {'id': 'round-id', 'winner': 'host'},
            None
        )

        response = client.post(
            '/api/game/ABC123/choice',
            json={'choice': 'rock'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['round']['winner'] == 'host'

    @patch('app.routes.api.Game')
    @patch('app.routes.api.GameService')
    def test_submit_invalid_choice(self, mock_service, mock_game, client):
        """Test submitting invalid choice."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'active',
            'host_session_id': 'host-id'
        }
        mock_service.get_player_role.return_value = 'host'
        mock_service.submit_choice.return_value = (None, "Invalid choice.")

        response = client.post(
            '/api/game/ABC123/choice',
            json={'choice': 'invalid'}
        )

        assert response.status_code == 400


class TestPlayAgainAPI:
    """Test play again API."""

    @patch('app.routes.api.Game')
    @patch('app.routes.api.GameService')
    def test_play_again(self, mock_service, mock_game, client):
        """Test creating a new game after completion."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        mock_game.get_by_code.return_value = {
            'id': 'old-game-id',
            'status': 'completed',
            'best_of': 3,
            'host_session_id': 'host-id'
        }
        mock_service.create_game.return_value = (
            {'game_code': 'NEW123', 'id': 'new-game-id'},
            None
        )

        response = client.post('/api/game/ABC123/play-again')

        assert response.status_code == 200
        data = response.get_json()
        assert data['game_code'] == 'NEW123'

    @patch('app.routes.api.Game')
    def test_play_again_only_host(self, mock_game, client):
        """Test only host can start new game."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'guest-id'

        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'status': 'completed',
            'host_session_id': 'host-id'
        }

        response = client.post('/api/game/ABC123/play-again')

        assert response.status_code == 403
