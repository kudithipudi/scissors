"""Test game routes."""
import pytest
from unittest.mock import patch


class TestIndexRoute:
    """Test landing page."""

    async def test_index(self, client):
        """Test landing page loads."""
        response = await client.get('/')
        assert response.status_code == 200
        assert b'Rock Paper Scissors' in response.content


class TestCreateGameRoute:
    """Test game creation route."""

    @patch('app.routers.game.GameService')
    async def test_create_game(self, mock_service, client):
        """Test creating a new game."""
        async def fake_create_game(best_of, host_session_id):
            return {'id': 'game-id', 'game_code': 'ABC123'}, None
        mock_service.create_game = fake_create_game

        response = await client.post(
            '/game/create',
            json={'best_of': 3}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['game_code'] == 'ABC123'

    @patch('app.routers.game.GameService')
    async def test_create_game_error(self, mock_service, client):
        """Test game creation error."""
        async def fake_create_game(best_of, host_session_id):
            return None, "Invalid game mode"
        mock_service.create_game = fake_create_game

        response = await client.post(
            '/game/create',
            json={'best_of': 7}
        )

        assert response.status_code == 400


class TestViewGameRoute:
    """Test viewing game page."""

    @patch('app.routers.game.QRService')
    @patch('app.routers.game.GameService')
    @patch('app.routers.game.Game')
    async def test_view_game_as_host(self, mock_game, mock_service, mock_qr, client, set_session):
        """Test viewing game as host."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'game_code': 'ABC123',
                'status': 'waiting',
                'host_session_id': 'host-id',
                'guest_session_id': None,
                'best_of': 3,
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_player_in_game.return_value = True
        mock_service.get_player_role.return_value = 'host'
        mock_qr.generate_qr_code.return_value = 'data:image/png;base64,fake'
        mock_qr.get_join_url.return_value = 'http://localhost/game/ABC123'

        response = await client.get('/game/ABC123')

        assert response.status_code == 200
        assert b'ABC123' in response.content

    @patch('app.routers.game.Game')
    async def test_view_game_not_found(self, mock_game, client):
        """Test viewing non-existent game."""
        async def fake_get_by_code(code):
            return None
        mock_game.get_by_code = fake_get_by_code

        response = await client.get('/game/FAKE')

        assert response.status_code == 404

    @patch('app.routers.game.GameService')
    @patch('app.routers.game.Game')
    async def test_view_game_auto_join(self, mock_game, mock_service, client, set_session):
        """Test auto-joining game as guest."""
        set_session(client, session_id='guest-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'game_code': 'ABC123',
                'status': 'waiting',
                'host_session_id': 'host-id',
                'guest_session_id': None,
                'best_of': 3,
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_player_in_game.return_value = False

        async def fake_join_game(code, session_id):
            return {
                'id': 'game-id',
                'game_code': 'ABC123',
                'status': 'active',
                'host_session_id': 'host-id',
                'guest_session_id': 'guest-id',
                'best_of': 3,
            }, None
        mock_service.join_game = fake_join_game
        mock_service.get_player_role.return_value = 'guest'

        response = await client.get('/game/ABC123')

        assert response.status_code == 200


class TestCancelGameRoute:
    """Test game cancellation route."""

    @patch('app.routers.game.GameService')
    async def test_cancel_game(self, mock_service, client, set_session):
        """Test canceling a game."""
        set_session(client, session_id='host-id')

        async def fake_cancel_game(code, session_id):
            return True, None
        mock_service.cancel_game = fake_cancel_game

        response = await client.post('/game/ABC123/cancel')

        assert response.status_code == 200

    @patch('app.routers.game.GameService')
    async def test_cancel_game_error(self, mock_service, client, set_session):
        """Test canceling game with error."""
        set_session(client, session_id='guest-id')

        async def fake_cancel_game(code, session_id):
            return False, "Only host can cancel"
        mock_service.cancel_game = fake_cancel_game

        response = await client.post('/game/ABC123/cancel')

        assert response.status_code == 400
