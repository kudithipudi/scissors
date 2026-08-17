"""Tests for the game-creation rate limiter."""
from starlette.requests import Request

from app.utils.rate_limit import client_ip, is_rate_limited


def _make_request(headers, client_addr=('127.0.0.1', 12345)):
    scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': 'POST',
        'scheme': 'http',
        'path': '/game/create',
        'raw_path': b'/game/create',
        'query_string': b'',
        'root_path': '',
        'headers': headers,
        'client': client_addr,
        'server': ('testserver', 80),
    }
    return Request(scope)


class TestClientIPResolution:
    """Test client IP resolution."""

    def test_prefers_first_x_forwarded_for_entry(self):
        request = _make_request([(b'x-forwarded-for', b'203.0.113.9, 10.0.0.1')])
        assert client_ip(request) == '203.0.113.9'

    def test_falls_back_to_socket_peer(self):
        request = _make_request([])
        assert client_ip(request) == '127.0.0.1'

    def test_prefers_x_real_ip_over_socket_peer(self):
        request = _make_request([(b'x-real-ip', b'203.0.113.10')])
        assert client_ip(request) == '203.0.113.10'

    def test_prefers_x_forwarded_for_over_x_real_ip(self):
        request = _make_request([
            (b'x-forwarded-for', b'203.0.113.9'),
            (b'x-real-ip', b'203.0.113.10'),
        ])
        assert client_ip(request) == '203.0.113.9'


class TestRateLimiter:
    """Test the check-and-record semantics of is_rate_limited."""

    async def test_allows_requests_under_limit(self, app):
        request = _make_request([(b'x-forwarded-for', b'203.0.113.50')])
        for _ in range(9):
            assert await is_rate_limited(request) is False

    async def test_blocks_at_limit(self, app):
        request = _make_request([(b'x-forwarded-for', b'203.0.113.51')])
        for _ in range(10):
            assert await is_rate_limited(request) is False
        assert await is_rate_limited(request) is True

    async def test_does_not_record_limited_request(self, app):
        request = _make_request([(b'x-forwarded-for', b'203.0.113.52')])
        for _ in range(10):
            await is_rate_limited(request)
        assert await is_rate_limited(request) is True
        # A limited request is not recorded, so it stays blocked (no growth).
        assert await is_rate_limited(request) is True

    async def test_limits_are_per_ip(self, app):
        request_a = _make_request([(b'x-forwarded-for', b'203.0.113.60')])
        request_b = _make_request([(b'x-forwarded-for', b'203.0.113.61')])
        for _ in range(10):
            assert await is_rate_limited(request_a) is False
        assert await is_rate_limited(request_a) is True
        assert await is_rate_limited(request_b) is False


class TestRateLimitedEndpoints:
    """Test the HTTP endpoints enforce the limit."""

    async def test_create_game_rate_limited(self, client):
        headers = {'X-Forwarded-For': '203.0.113.70'}
        for _ in range(10):
            resp = await client.post('/game/create', json={'best_of': 3}, headers=headers)
            assert resp.status_code == 200

        resp = await client.post('/game/create', json={'best_of': 3}, headers=headers)
        assert resp.status_code == 429
        assert 'error' in resp.json()

    async def test_rate_limit_is_per_ip(self, client):
        for _ in range(10):
            resp = await client.post('/game/create', json={'best_of': 3}, headers={'X-Forwarded-For': '203.0.113.71'})
            assert resp.status_code == 200

        resp = await client.post('/game/create', json={'best_of': 3}, headers={'X-Forwarded-For': '203.0.113.72'})
        assert resp.status_code == 200

    async def test_play_again_rate_limited(self, client, set_session):
        set_session(client, session_id='host-id')
        headers = {'X-Forwarded-For': '203.0.113.73'}
        for _ in range(10):
            resp = await client.post('/api/game/NOPE123/play-again', headers=headers)
            assert resp.status_code == 404  # recorded but game doesn't exist

        resp = await client.post('/api/game/NOPE123/play-again', headers=headers)
        assert resp.status_code == 429
