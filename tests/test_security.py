"""Tests for security hardening response headers."""


class TestSecurityHeaders:
    """Test the security headers added by the middleware."""

    async def test_security_headers_on_page(self, client):
        resp = await client.get('/')
        assert resp.status_code == 200
        assert resp.headers['X-Content-Type-Options'] == 'nosniff'
        assert resp.headers['X-Frame-Options'] == 'DENY'
        assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'

        policy = resp.headers['Permissions-Policy']
        # Motion sensors must stay enabled for shake detection.
        assert 'accelerometer=(self)' in policy
        assert 'gyroscope=(self)' in policy
        assert 'magnetometer=(self)' in policy
        # Everything else is locked down.
        assert 'camera=()' in policy
        assert 'microphone=()' in policy
        assert 'geolocation=()' in policy

    async def test_security_headers_on_api_response(self, client):
        resp = await client.get('/api/stats')
        assert resp.status_code == 200
        assert resp.headers['X-Content-Type-Options'] == 'nosniff'

    async def test_security_headers_on_error_page(self, client):
        resp = await client.get('/nonexistent')
        assert resp.status_code == 404
        assert resp.headers['X-Content-Type-Options'] == 'nosniff'
        assert resp.headers['X-Frame-Options'] == 'DENY'
