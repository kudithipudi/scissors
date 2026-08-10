"""Pytest configuration and fixtures."""
import base64
import json
import os

# Must be set before app.config / app.main are imported anywhere, since the
# SessionMiddleware bakes SECRET_KEY in at import time.
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('SESSION_COOKIE_SECURE', 'false')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin-password')

import itsdangerous
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db import init_db
from app.utils.rate_limit import reset_rate_limiter

TEST_SECRET_KEY = os.environ['SECRET_KEY']


@pytest_asyncio.fixture
async def app(tmp_path):
    """Point settings at a throwaway SQLite file and yield the FastAPI app."""
    settings.DB_PATH = str(tmp_path / 'scissors_test.db')
    reset_rate_limiter()
    await init_db()

    from app.main import app as fastapi_app
    yield fastapi_app


@pytest_asyncio.fixture
async def client(app):
    """Async test client (httpx over ASGI, no real network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def set_session():
    """Directly set the signed session cookie, equivalent to Flask's session_transaction()."""

    def _set(client, **data):
        signer = itsdangerous.TimestampSigner(TEST_SECRET_KEY)
        payload = base64.b64encode(json.dumps(data).encode("utf-8"))
        signed = signer.sign(payload).decode("utf-8")
        # Clear first: httpx stores the server's Set-Cookie under a normalized
        # domain (e.g. "testserver.local"), distinct from a bare .set() call,
        # so without this the stale cookie would still be sent alongside ours.
        client.cookies.clear()
        client.cookies.set("session", signed)

    return _set


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
