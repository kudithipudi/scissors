"""Test game routes."""
import pytest
from unittest.mock import patch


class TestIndexRoute:
    """Test landing page."""

    def test_index(self, client):
        """Test landing page loads."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Rock Paper Scissors' in response.data


class TestCreateGameRoute:
    """Test game creation route."""

    @patch('app.routes.game.GameService')
    def test_create_game(self, mock_service, client):
        """Test creating a new game."""
        mock_service.create_game.return_value = (
            {'id': 'game-id', 'game_code': 'ABC123'},
            None
        )

        response = client.post(
            '/game/create',
            json={'best_of': 3}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['game_code'] == 'ABC123'

    @patch('app.routes.game.GameService')
    def test_create_game_error(self, mock_service, client):
        """Test game creation error."""
        mock_service.create_game.return_value = (
            None,
            "Invalid game mode"
        )

        response = client.post(
            '/game/create',
            json={'best_of': 7}
        )

        assert response.status_code == 400


class TestViewGameRoute:
    """Test viewing game page."""

    @patch('app.routes.game.Game')
    @patch('app.routes.game.GameService')
    @patch('app.routes.game.QRService')
    def test_view_game_as_host(self, mock_qr, mock_service, mock_game, client):
        """Test viewing game as host."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'game_code': 'ABC123',
            'status': 'waiting',
            'host_session_id': 'host-id',
            'guest_session_id': None,
            'best_of': 3
        }
        mock_service.is_player_in_game.return_value = True
        mock_service.get_player_role.return_value = 'host'
        mock_qr.generate_qr_code.return_value = 'data:image/png;base64,fake'
        mock_qr.get_join_url.return_value = 'http://localhost/game/ABC123'

        response = client.get('/game/ABC123')

        assert response.status_code == 200
        assert b'ABC123' in response.data

    @patch('app.routes.game.Game')
    def test_view_game_not_found(self, mock_game, client):
        """Test viewing non-existent game."""
        mock_game.get_by_code.return_value = None

        response = client.get('/game/FAKE')

        assert response.status_code == 404

    @patch('app.routes.game.Game')
    @patch('app.routes.game.GameService')
    def test_view_game_auto_join(self, mock_service, mock_game, client):
        """Test auto-joining game as guest."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'guest-id'

        mock_game.get_by_code.return_value = {
            'id': 'game-id',
            'game_code': 'ABC123',
            'status': 'waiting',
            'host_session_id': 'host-id',
            'guest_session_id': None,
            'best_of': 3
        }
        mock_service.is_player_in_game.return_value = False
        mock_service.join_game.return_value = (
            {
                'id': 'game-id',
                'status': 'active',
                'guest_session_id': 'guest-id'
            },
            None
        )
        mock_service.get_player_role.return_value = 'guest'

        response = client.get('/game/ABC123')

        assert response.status_code == 200


class TestCancelGameRoute:
    """Test game cancellation route."""

    @patch('app.routes.game.GameService')
    def test_cancel_game(self, mock_service, client):
        """Test canceling a game."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        mock_service.cancel_game.return_value = (True, None)

        response = client.post('/game/ABC123/cancel')

        assert response.status_code == 200

    @patch('app.routes.game.GameService')
    def test_cancel_game_error(self, mock_service, client):
        """Test canceling game with error."""
        with client.session_transaction() as sess:
            sess['session_id'] = 'guest-id'

        mock_service.cancel_game.return_value = (
            False,
            "Only host can cancel"
        )

        response = client.post('/game/ABC123/cancel')

        assert response.status_code == 400
