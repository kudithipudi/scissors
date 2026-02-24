"""Pytest configuration and fixtures."""
import pytest
import os
from unittest.mock import MagicMock, patch
from app import create_app


@pytest.fixture
def app():
    """Create application for testing."""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
    os.environ['SUPABASE_KEY'] = 'test-key'

    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'

    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    with patch('app.services.supabase_service.create_client') as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_game():
    """Sample game data for testing."""
    return {
        'id': '123e4567-e89b-12d3-a456-426614174000',
        'game_code': 'ABC123',
        'status': 'waiting',
        'best_of': 3,
        'host_session_id': 'host-session-id',
        'guest_session_id': None,
        'winner': None,
        'created_at': '2026-02-13T10:00:00Z',
        'started_at': None,
        'completed_at': None,
        'expires_at': '2026-02-13T10:02:00Z'
    }


@pytest.fixture
def sample_round():
    """Sample round data for testing."""
    return {
        'id': '123e4567-e89b-12d3-a456-426614174001',
        'game_id': '123e4567-e89b-12d3-a456-426614174000',
        'round_number': 1,
        'host_choice': None,
        'guest_choice': None,
        'host_shakes': 0,
        'guest_shakes': 0,
        'winner': None,
        'created_at': '2026-02-13T10:00:00Z',
        'completed_at': None
    }


@pytest.fixture
def active_game(sample_game):
    """Sample active game with both players."""
    game = sample_game.copy()
    game['status'] = 'active'
    game['guest_session_id'] = 'guest-session-id'
    game['started_at'] = '2026-02-13T10:00:30Z'
    return game
