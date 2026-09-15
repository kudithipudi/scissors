"""Test API endpoints."""
import pytest
from unittest.mock import patch


class TestStatsAPI:
    """Test statistics API."""

    @patch('app.routers.api.Statistics')
    async def test_get_stats(self, mock_stats, client):
        """Test getting public statistics."""
        async def fake_active_count():
            return 5
        async def fake_total_count():
            return 100
        mock_stats.get_active_game_count = fake_active_count
        mock_stats.get_game_count = fake_total_count

        response = await client.get('/api/stats')

        assert response.status_code == 200
        data = response.json()
        assert data['active_games'] == 5
        assert data['total_games'] == 100


class TestGameStateAPI:
    """Test game state API."""

    @patch('app.routers.api.GameService')
    async def test_get_game_state(self, mock_service, client):
        """Test getting game state."""
        async def fake_get_game_state(code):
            return {
                'game': {'id': 'game-id', 'status': 'active'},
                'rounds': [],
                'current_round': 1
            }
        mock_service.get_game_state = fake_get_game_state

        response = await client.get('/api/game/ABC123/state')

        assert response.status_code == 200
        data = response.json()
        assert data['game']['status'] == 'active'

    @patch('app.routers.api.GameService')
    async def test_get_game_state_not_found(self, mock_service, client):
        """Test getting state of non-existent game."""
        async def fake_get_game_state(code):
            return None
        mock_service.get_game_state = fake_get_game_state

        response = await client.get('/api/game/FAKE/state')

        assert response.status_code == 404


class TestShakeAPI:
    """Test shake recording API."""

    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_record_shake(self, mock_game, mock_service, client, set_session):
        """Test recording shake count."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'status': 'active',
                'host_session_id': 'host-id',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.get_player_role.return_value = 'host'

        async def fake_record_shake(code, role, count):
            return True, None
        mock_service.record_shake = fake_record_shake

        response = await client.post(
            '/api/game/ABC123/shake',
            json={'shake_count': 2}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['shake_count'] == 2

    async def test_record_shake_no_session(self, client):
        """Test recording shake without session."""
        response = await client.post(
            '/api/game/ABC123/shake',
            json={'shake_count': 2}
        )

        assert response.status_code == 401


class TestChoiceAPI:
    """Test choice submission API."""

    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_submit_choice(self, mock_game, mock_service, client, set_session):
        """Test submitting a choice."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'status': 'active',
                'host_session_id': 'host-id',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.get_player_role.return_value = 'host'

        async def fake_submit_choice(code, role, choice):
            return {'id': 'round-id', 'winner': 'host'}, None
        mock_service.submit_choice = fake_submit_choice

        response = await client.post(
            '/api/game/ABC123/choice',
            json={'choice': 'rock'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['round']['winner'] == 'host'

    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_submit_invalid_choice(self, mock_game, mock_service, client, set_session):
        """Test submitting invalid choice."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'status': 'active',
                'host_session_id': 'host-id',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.get_player_role.return_value = 'host'

        async def fake_submit_choice(code, role, choice):
            return None, "Invalid choice."
        mock_service.submit_choice = fake_submit_choice

        response = await client.post(
            '/api/game/ABC123/choice',
            json={'choice': 'invalid'}
        )

        assert response.status_code == 400


class TestPlayAgainAPI:
    """Test play again API."""

    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_play_again(self, mock_game, mock_service, client, set_session):
        """Test creating a new game after completion."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'old-game-id',
                'status': 'completed',
                'best_of': 3,
                'host_session_id': 'host-id',
            }
        mock_game.get_by_code = fake_get_by_code

        async def fake_create_game(best_of, host_session_id, vs_computer=False):
            return {'game_code': 'NEW123', 'id': 'new-game-id'}, None
        mock_service.create_game = fake_create_game

        response = await client.post('/api/game/ABC123/play-again')

        assert response.status_code == 200
        data = response.json()
        assert data['game_code'] == 'NEW123'

    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_play_again_preserves_vs_computer(self, mock_game, mock_service, client, set_session):
        """Test rematching a solo vs-computer game stays vs-computer."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'old-game-id',
                'status': 'completed',
                'best_of': 3,
                'host_session_id': 'host-id',
                'guest_session_id': 'COMPUTER',
            }
        mock_game.get_by_code = fake_get_by_code

        received = {}

        async def fake_create_game(best_of, host_session_id, vs_computer=False):
            received['vs_computer'] = vs_computer
            return {'game_code': 'NEW123', 'id': 'new-game-id'}, None
        mock_service.create_game = fake_create_game

        response = await client.post('/api/game/ABC123/play-again')

        assert response.status_code == 200
        assert received['vs_computer'] is True

    @patch('app.routers.api.Game')
    async def test_play_again_only_host(self, mock_game, client, set_session):
        """Test only host can start new game."""
        set_session(client, session_id='guest-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'status': 'completed',
                'host_session_id': 'host-id',
            }
        mock_game.get_by_code = fake_get_by_code

        response = await client.post('/api/game/ABC123/play-again')

        assert response.status_code == 403
