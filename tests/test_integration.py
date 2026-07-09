"""Integration tests for complete game flow (against a real SQLite test db)."""
import pytest
from unittest.mock import patch


class TestCompleteGameFlow:
    """Test complete game from creation to completion."""

    async def test_full_game_flow_best_of_one(self, client, set_session):
        """Test complete best-of-1 game flow."""
        # Step 1: Host creates game
        set_session(client, session_id='host-id')

        create_response = await client.post(
            '/game/create',
            json={'best_of': 1}
        )

        assert create_response.status_code == 200
        game_code = create_response.json()['game_code']

        # Step 2: Guest joins game (auto-join on view while status == waiting)
        set_session(client, session_id='guest-id')

        join_response = await client.get(f'/game/{game_code}')
        assert join_response.status_code == 200

        # Step 3: Both players make choices
        # Host chooses rock
        set_session(client, session_id='host-id')

        host_choice = await client.post(
            f'/api/game/{game_code}/choice',
            json={'choice': 'rock'}
        )
        assert host_choice.status_code == 200

        # Guest chooses scissors -> rock beats scissors, best_of=1 completes the game
        set_session(client, session_id='guest-id')

        guest_choice = await client.post(
            f'/api/game/{game_code}/choice',
            json={'choice': 'scissors'}
        )
        assert guest_choice.status_code == 200
        assert guest_choice.json()['success'] is True

        # Game state should now be completed with host as the winner
        state_response = await client.get(f'/api/game/{game_code}/state')
        assert state_response.status_code == 200
        state = state_response.json()
        assert state['game']['status'] == 'completed'
        assert state['game']['winner'] == 'host'


class TestMultipleGames:
    """Test multiple concurrent games."""

    async def test_concurrent_games(self, client, set_session):
        """Test multiple games running concurrently get distinct codes."""
        codes = []
        for i in range(2):
            set_session(client, session_id=f'host-{i}')

            response = await client.post('/game/create', json={'best_of': 3})
            assert response.status_code == 200
            codes.append(response.json()['game_code'])

        assert len(set(codes)) == 2


class TestErrorHandling:
    """Test error handling throughout the app."""

    async def test_404_error_page(self, client):
        """Test 404 error page."""
        response = await client.get('/nonexistent')
        assert response.status_code == 404

    @patch('app.routers.game.Game')
    async def test_game_not_found(self, mock_game, client):
        """Test accessing non-existent game."""
        async def fake_get_by_code(code):
            return None
        mock_game.get_by_code = fake_get_by_code

        response = await client.get('/game/NOTFOUND')
        assert response.status_code == 404

    async def test_invalid_json_request(self, client):
        """Test invalid JSON in request."""
        response = await client.post(
            '/game/create',
            content='invalid json',
            headers={'content-type': 'application/json'},
        )
        assert response.status_code in [400, 500]  # Should handle gracefully
