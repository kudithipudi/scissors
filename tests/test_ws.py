"""Tests for the real-time WebSocket channel and the reaction endpoint.

The rest of the suite drives the app through httpx's ASGITransport, which
cannot speak the WebSocket protocol. These tests therefore use Starlette's
*synchronous* TestClient, which is the supported way to exercise WS routes.

Everything here runs inside `with TestClient(app)` on purpose: that gives the
whole test one shared event loop (lifespan, HTTP requests and the open socket),
matching production, where gunicorn runs exactly one UvicornWorker. Driving the
socket and the HTTP requests from two different loops would leave the
asyncio.Queue wakeup stranded and the test would hang.
"""
import base64
import json

import itsdangerous
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.services import game_events
from tests.conftest import TEST_SECRET_KEY


def _session_cookie(session_id: str) -> str:
    """Build a signed session cookie for an anonymous player."""
    signer = itsdangerous.TimestampSigner(TEST_SECRET_KEY)
    payload = base64.b64encode(json.dumps({'session_id': session_id}).encode('utf-8'))
    return signer.sign(payload).decode('utf-8')


def _as(client: TestClient, session_id: str) -> None:
    """Point the client at a given anonymous session."""
    client.cookies.clear()
    client.cookies.set('session', _session_cookie(session_id))


@pytest.fixture
def ws_client(tmp_path):
    """A sync TestClient backed by a throwaway SQLite file.

    The schema is applied by the app's own lifespan (`init_db()` on startup),
    which is why this deliberately does not spin up an extra event loop of its
    own: the suite's async tests leave their pytest-asyncio loops unclosed, and
    creating another loop here makes those get collected mid-test, which
    `filterwarnings = error` in pytest.ini turns into a ResourceWarning
    failure. Staying on one loop keeps this test module self-contained.
    """
    settings.DB_PATH = str(tmp_path / 'scissors_ws_test.db')

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as client:
        yield client


def _start_game(client: TestClient, best_of: int = 1) -> str:
    """Create a game as `host-ws` and join it as `guest-ws`; return the code."""
    _as(client, 'host-ws')
    response = client.post('/game/create', json={'best_of': best_of})
    assert response.status_code == 200, response.text
    game_code = response.json()['game_code']

    _as(client, 'guest-ws')
    response = client.post(f'/game/{game_code}/join')
    assert response.status_code == 200, response.text

    return game_code


class TestGameEvents:
    """The in-process pub/sub itself (async: needs a running loop for Queue)."""

    def test_publish_without_subscribers_is_a_noop(self):
        assert game_events.publish('NOBODY', {'type': 'state'}) == 0

    async def test_subscribe_receives_then_unsubscribe_stops(self):
        queue = game_events.subscribe('ABC123')
        assert game_events.subscriber_count('ABC123') == 1

        assert game_events.publish('ABC123', {'type': 'state'}) == 1
        assert queue.get_nowait() == {'type': 'state'}

        game_events.unsubscribe('ABC123', queue)
        assert game_events.subscriber_count('ABC123') == 0
        assert game_events.publish('ABC123', {'type': 'state'}) == 0

    async def test_full_queue_drops_events_instead_of_raising(self):
        """A wedged subscriber must never break a game mutation."""
        queue = game_events.subscribe('FULLQ')
        try:
            for _ in range(game_events.QUEUE_MAXSIZE):
                queue.put_nowait({'type': 'state'})
            # Queue is full: publish drops silently, delivering to nobody.
            assert game_events.publish('FULLQ', {'type': 'state'}) == 0
        finally:
            game_events.unsubscribe('FULLQ', queue)


class TestGameWebSocket:
    """The /ws/game/{code} route."""

    def test_player_receives_state_event_when_round_completes(self, ws_client):
        """The critical path: the reveal poke reaches the waiting player."""
        game_code = _start_game(ws_client, best_of=1)

        # Host locks in first, then listens.
        _as(ws_client, 'host-ws')
        response = ws_client.post(f'/api/game/{game_code}/choice', json={'choice': 'rock'})
        assert response.status_code == 200, response.text

        with ws_client.websocket_connect(f'/ws/game/{game_code}') as websocket:
            # Guest's choice completes the round -> publish() fires.
            _as(ws_client, 'guest-ws')
            response = ws_client.post(
                f'/api/game/{game_code}/choice', json={'choice': 'scissors'}
            )
            assert response.status_code == 200, response.text

            message = websocket.receive_json()
            assert message == {'type': 'state'}

    def test_guest_join_pokes_the_waiting_host(self, ws_client):
        _as(ws_client, 'host-ws')
        response = ws_client.post('/game/create', json={'best_of': 3})
        game_code = response.json()['game_code']

        with ws_client.websocket_connect(f'/ws/game/{game_code}') as websocket:
            _as(ws_client, 'guest-ws')
            response = ws_client.post(f'/game/{game_code}/join')
            assert response.status_code == 200, response.text

            assert websocket.receive_json() == {'type': 'state'}

    def test_cancel_pokes_the_other_player(self, ws_client):
        game_code = _start_game(ws_client, best_of=3)

        _as(ws_client, 'guest-ws')
        with ws_client.websocket_connect(f'/ws/game/{game_code}') as websocket:
            _as(ws_client, 'host-ws')
            response = ws_client.post(f'/game/{game_code}/cancel')
            assert response.status_code == 200, response.text

            assert websocket.receive_json() == {'type': 'state'}

    def test_reaction_is_delivered_over_the_socket(self, ws_client):
        game_code = _start_game(ws_client, best_of=3)

        _as(ws_client, 'host-ws')
        with ws_client.websocket_connect(f'/ws/game/{game_code}') as websocket:
            _as(ws_client, 'guest-ws')
            response = ws_client.post(
                f'/api/game/{game_code}/react', json={'emoji': '🔥'}
            )
            assert response.status_code == 200, response.text

            assert websocket.receive_json() == {
                'type': 'reaction',
                'from': 'guest',
                'emoji': '🔥',
            }

    def test_non_player_is_rejected(self, ws_client):
        game_code = _start_game(ws_client, best_of=1)

        _as(ws_client, 'random-bystander')
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with ws_client.websocket_connect(f'/ws/game/{game_code}'):
                pass  # pragma: no cover - connection must never be accepted

        assert excinfo.value.code == 4403

    def test_session_less_client_is_rejected(self, ws_client):
        game_code = _start_game(ws_client, best_of=1)

        ws_client.cookies.clear()
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with ws_client.websocket_connect(f'/ws/game/{game_code}'):
                pass  # pragma: no cover - connection must never be accepted

        assert excinfo.value.code == 4403

    def test_unknown_game_is_rejected(self, ws_client):
        _as(ws_client, 'host-ws')
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with ws_client.websocket_connect('/ws/game/NOSUCH'):
                pass  # pragma: no cover - connection must never be accepted

        assert excinfo.value.code == 4403

    def test_subscriber_is_cleaned_up_on_disconnect(self, ws_client):
        game_code = _start_game(ws_client, best_of=1)

        _as(ws_client, 'host-ws')
        with ws_client.websocket_connect(f'/ws/game/{game_code}'):
            pass

        # The server-side task unsubscribes in its finally block.
        for _ in range(50):
            if game_events.subscriber_count(game_code) == 0:
                break
            ws_client.get('/health')
        assert game_events.subscriber_count(game_code) == 0


class TestReactionEndpoint:
    """POST /api/game/{code}/react — allowlist, auth and rate limiting."""

    def test_rejects_emoji_outside_the_allowlist(self, ws_client):
        game_code = _start_game(ws_client, best_of=1)

        _as(ws_client, 'host-ws')
        response = ws_client.post(
            f'/api/game/{game_code}/react', json={'emoji': '<script>'}
        )
        assert response.status_code == 400

    def test_requires_a_session(self, ws_client):
        game_code = _start_game(ws_client, best_of=1)

        ws_client.cookies.clear()
        response = ws_client.post(f'/api/game/{game_code}/react', json={'emoji': '🔥'})
        assert response.status_code == 401

    def test_rejects_non_players(self, ws_client):
        game_code = _start_game(ws_client, best_of=1)

        _as(ws_client, 'random-bystander')
        response = ws_client.post(f'/api/game/{game_code}/react', json={'emoji': '🔥'})
        assert response.status_code == 403

    def test_unknown_game_is_404(self, ws_client):
        _as(ws_client, 'host-ws')
        response = ws_client.post('/api/game/NOSUCH/react', json={'emoji': '🔥'})
        assert response.status_code == 404

    def test_rate_limits_repeat_reactions(self, ws_client):
        game_code = _start_game(ws_client, best_of=1)

        _as(ws_client, 'host-ws')
        first = ws_client.post(f'/api/game/{game_code}/react', json={'emoji': '😂'})
        second = ws_client.post(f'/api/game/{game_code}/react', json={'emoji': '😂'})

        assert first.status_code == 200
        assert second.status_code == 429
