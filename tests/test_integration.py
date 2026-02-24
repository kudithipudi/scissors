"""Integration tests for complete game flow."""
import pytest
from unittest.mock import patch, MagicMock


class TestCompleteGameFlow:
    """Test complete game from creation to completion."""

    @patch('app.services.supabase_service.create_client')
    def test_full_game_flow_best_of_one(self, mock_supabase, client):
        """Test complete best-of-1 game flow."""
        # Mock Supabase client
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock game creation
        game_data = {
            'id': 'game-id',
            'game_code': 'ABC123',
            'status': 'waiting',
            'best_of': 1,
            'host_session_id': 'host-id',
            'guest_session_id': None
        }
        mock_client.table().insert().execute.return_value = MagicMock(
            data=[game_data]
        )
        mock_client.table().select().eq().execute.return_value = MagicMock(
            data=[game_data]
        )

        # Step 1: Host creates game
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        create_response = client.post(
            '/game/create',
            json={'best_of': 1}
        )

        assert create_response.status_code == 200
        game_code = create_response.get_json()['game_code']

        # Step 2: Guest joins game
        with client.session_transaction() as sess:
            sess['session_id'] = 'guest-id'

        # Update mock for active game
        active_game = game_data.copy()
        active_game['status'] = 'active'
        active_game['guest_session_id'] = 'guest-id'
        mock_client.table().select().eq().execute.return_value = MagicMock(
            data=[active_game]
        )

        join_response = client.get(f'/game/{game_code}')
        assert join_response.status_code == 200

        # Step 3: Both players make choices
        # Mock round data
        round_data = {
            'id': 'round-id',
            'game_id': 'game-id',
            'round_number': 1,
            'host_choice': None,
            'guest_choice': None
        }
        mock_client.table().select().eq().order().execute.return_value = MagicMock(
            data=[round_data]
        )

        # Host chooses rock
        with client.session_transaction() as sess:
            sess['session_id'] = 'host-id'

        host_choice = client.post(
            f'/api/game/{game_code}/choice',
            json={'choice': 'rock'}
        )
        assert host_choice.status_code == 200

        # Guest chooses scissors
        with client.session_transaction() as sess:
            sess['session_id'] = 'guest-id'

        guest_choice = client.post(
            f'/api/game/{game_code}/choice',
            json={'choice': 'scissors'}
        )
        assert guest_choice.status_code == 200


class TestMultipleGames:
    """Test multiple concurrent games."""

    @patch('app.services.supabase_service.create_client')
    def test_concurrent_games(self, mock_supabase, client):
        """Test multiple games running concurrently."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Create two games
        for i in range(2):
            with client.session_transaction() as sess:
                sess['session_id'] = f'host-{i}'

            game_data = {
                'id': f'game-{i}',
                'game_code': f'GAME{i}',
                'status': 'waiting',
                'best_of': 3,
                'host_session_id': f'host-{i}'
            }
            mock_client.table().insert().execute.return_value = MagicMock(
                data=[game_data]
            )
            mock_client.table().select().eq().execute.return_value = MagicMock(
                data=[]  # No existing game
            )

            response = client.post('/game/create', json={'best_of': 3})
            assert response.status_code == 200


class TestErrorHandling:
    """Test error handling throughout the app."""

    def test_404_error_page(self, client):
        """Test 404 error page."""
        response = client.get('/nonexistent')
        assert response.status_code == 404

    @patch('app.routes.game.Game')
    def test_game_not_found(self, mock_game, client):
        """Test accessing non-existent game."""
        mock_game.get_by_code.return_value = None

        response = client.get('/game/NOTFOUND')
        assert response.status_code == 404

    def test_invalid_json_request(self, client):
        """Test invalid JSON in request."""
        response = client.post(
            '/game/create',
            data='invalid json',
            content_type='application/json'
        )
        assert response.status_code in [400, 500]  # Should handle gracefully
