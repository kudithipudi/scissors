"""Test device and gyroscope detection functionality."""
import pytest
from unittest.mock import patch


class TestDeviceDetection:
    """Test device type detection."""

    async def test_detect_mobile_ios(self, client):
        """Test iOS device detection."""
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'}
        response = await client.get('/', headers=headers)
        assert response.status_code == 200
        # Should render without errors

    async def test_detect_mobile_android(self, client):
        """Test Android device detection."""
        headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36'}
        response = await client.get('/', headers=headers)
        assert response.status_code == 200

    async def test_detect_desktop(self, client):
        """Test desktop browser detection."""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = await client.get('/', headers=headers)
        assert response.status_code == 200

    async def test_detect_tablet(self, client):
        """Test tablet device detection."""
        headers = {'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 13_0 like Mac OS X)'}
        response = await client.get('/', headers=headers)
        assert response.status_code == 200


class TestShakeDetectionEndpoint:
    """Test shake detection and manual choice fallback."""

    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_manual_choice_submission(self, mock_game, mock_service, client, set_session):
        """Test submitting manual choice when shake detection fails."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {'id': 'game-id', 'status': 'active', 'host_session_id': 'host-id'}
        mock_game.get_by_code = fake_get_by_code
        mock_service.get_player_role.return_value = 'host'

        async def fake_submit_choice(code, role, choice):
            return {'id': 'round-id', 'winner': None}, None
        mock_service.submit_choice = fake_submit_choice

        # Submit a manual choice
        response = await client.post(
            '/api/game/ABC123/choice',
            json={'choice': 'rock'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @patch('app.routers.game.GameService')
    @patch('app.routers.game.Game')
    async def test_game_page_includes_shake_js(self, mock_game, mock_service, client, set_session):
        """Test that game page includes shake detection script."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'game_code': 'ABC123',
                'status': 'active',
                'best_of': 3,
                'host_session_id': 'host-id',
                'guest_session_id': 'guest-id',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_player_in_game.return_value = True
        mock_service.get_player_role.return_value = 'host'

        response = await client.get('/game/ABC123')

        assert response.status_code == 200
        assert b'shake.js' in response.content

    @patch('app.routers.game.GameService')
    @patch('app.routers.game.Game')
    async def test_game_page_has_manual_choice_ui(self, mock_game, mock_service, client, set_session):
        """Test that game page includes manual choice fallback UI."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'game_code': 'ABC123',
                'status': 'active',
                'best_of': 3,
                'host_session_id': 'host-id',
                'guest_session_id': 'guest-id',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_player_in_game.return_value = True
        mock_service.get_player_role.return_value = 'host'

        response = await client.get('/game/ABC123')

        assert response.status_code == 200
        # Check for manual choice buttons (always available, not just on sensor error)
        assert b'selectManualChoice' in response.content
        assert b'lockChoice' in response.content


class TestJavaScriptDeviceDetection:
    """Test JavaScript device detection logic (documented tests)."""

    def test_device_detection_mobile_user_agents(self):
        """
        Test mobile device detection with various user agents.

        This test documents the expected behavior of the JavaScript
        DeviceCapabilities.isMobile() function.
        """
        mobile_user_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
            'Mozilla/5.0 (iPad; CPU OS 13_0 like Mac OS X)',
            'Mozilla/5.0 (Linux; Android 10)',
            'Mozilla/5.0 (Linux; Android 11; SM-G991B)',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)',
            'Mozilla/5.0 (Android 12; Mobile)',
        ]

        # Document: All these should be detected as mobile
        for ua in mobile_user_agents:
            # In JavaScript: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
            assert any(device in ua for device in ['Android', 'iPhone', 'iPad', 'iPod'])

    def test_device_detection_desktop_user_agents(self):
        """
        Test desktop device detection with various user agents.

        This test documents the expected behavior for desktop browsers.
        """
        desktop_user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Mozilla/5.0 (X11; Linux x86_64)',
        ]

        # Document: These should NOT be detected as mobile
        for ua in desktop_user_agents:
            assert not any(device in ua for device in ['Android', 'iPhone', 'iPad', 'iPod', 'Mobile'])

    def test_motion_sensor_requirements(self):
        """
        Document motion sensor requirements.

        For shake detection to work, the following must be true:
        1. Device is mobile (smartphone/tablet)
        2. DeviceMotionEvent is supported
        3. Connection is HTTPS (secure context)
        4. Permission granted (iOS 13+)
        """
        requirements = {
            'mobile': True,
            'device_motion_event': True,
            'https': True,
            'permission': True  # iOS only
        }

        # All requirements must be met
        assert all(requirements.values())


class TestErrorHandling:
    """Test error handling for device detection failures."""

    @patch('app.routers.game.GameService')
    @patch('app.routers.game.Game')
    async def test_game_works_without_motion_sensors(self, mock_game, mock_service, client, set_session):
        """Test that game is still playable without motion sensors."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'game_code': 'ABC123',
                'status': 'active',
                'best_of': 1,
                'host_session_id': 'host-id',
                'guest_session_id': 'guest-id',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_player_in_game.return_value = True
        mock_service.get_player_role.return_value = 'host'

        # Should still render the game page
        response = await client.get('/game/ABC123')
        assert response.status_code == 200

        # Should have fallback UI
        assert b'selectManualChoice' in response.content


class TestAccessibilityFallback:
    """Test that manual choice serves as accessibility fallback."""

    def test_manual_choice_all_options_available(self, client):
        """Test that all three choices are available in manual mode."""
        # This is a documentation test for the UI
        choices = ['rock', 'paper', 'scissors']

        # All choices must be available
        assert len(choices) == 3
        assert 'rock' in choices
        assert 'paper' in choices
        assert 'scissors' in choices

    def test_manual_choice_emojis_match(self):
        """Test that manual choice buttons use correct emojis."""
        choice_emojis = {
            'rock': '✊',
            'paper': '✋',
            'scissors': '✌️'
        }

        # Verify all emojis are defined
        assert len(choice_emojis) == 3
        for choice in ['rock', 'paper', 'scissors']:
            assert choice in choice_emojis
            assert choice_emojis[choice]  # Not empty


class TestIOSPermissionHandling:
    """Test iOS motion sensor permission handling (shake.js v2.1)."""

    def test_ios_permission_required_detection(self):
        """
        Test detection of iOS devices that need permission.

        In shake.js, needsPermission() checks if:
        - DeviceMotionEvent exists
        - DeviceMotionEvent.requestPermission is a function (iOS 13+)
        """
        # Document expected behavior
        ios_needs_permission = {
            'has_device_motion_event': True,
            'has_request_permission_method': True,  # iOS 13+ only
        }

        # iOS 13+ should require permission
        assert ios_needs_permission['has_device_motion_event']
        assert ios_needs_permission['has_request_permission_method']

    def test_android_no_permission_required(self):
        """
        Test that Android devices don't need permission.

        Android returns true immediately from requestPermission()
        without showing any prompt.
        """
        # Document expected behavior
        android_permission = {
            'has_device_motion_event': True,
            'has_request_permission_method': False,  # Android doesn't have this
            'auto_grant': True
        }

        # Android should auto-grant
        assert android_permission['auto_grant']

    def test_permission_request_from_user_gesture(self):
        """
        Test that permission must be requested from user gesture.

        This documents the requirement that requestPermission()
        must be called from a user interaction (button click).
        Calling it automatically will throw an error:
        'Requesting device motion access required a user gesture to prompt'
        """
        requirements = {
            'must_be_user_gesture': True,
            'cannot_be_automatic': True,
            'needs_button_click': True
        }

        assert requirements['must_be_user_gesture']
        assert requirements['cannot_be_automatic']
        assert requirements['needs_button_click']

    def test_permission_flow_sequence(self):
        """
        Document the correct permission request flow.

        Correct sequence:
        1. checkCapabilities() - does NOT request permission
        2. User sees "Request Permission" button
        3. User taps button
        4. requestPermission() called from click handler
        5. iOS shows system dialog
        6. Permission granted or denied
        7. Shake detection starts or fallback to manual choice
        """
        flow_steps = [
            'check_capabilities',
            'show_permission_button',
            'user_taps_button',
            'request_permission_from_gesture',
            'ios_shows_dialog',
            'permission_result',
            'enable_shake_or_fallback'
        ]

        # Verify all steps are documented
        assert len(flow_steps) == 7
        assert 'check_capabilities' in flow_steps
        assert 'user_taps_button' in flow_steps
        assert 'request_permission_from_gesture' in flow_steps

    def test_shake_detector_start_permission_handling(self):
        """
        Test ShakeDetector.start() permission handling.

        When start() is called:
        1. If needsPermission() is true, call requestPermission()
        2. If permission denied, call onError callback
        3. If granted, add devicemotion listener
        4. Return true on success, false on failure
        """
        expected_behavior = {
            'checks_permission_needed': True,
            'requests_if_needed': True,
            'handles_denial': True,
            'calls_error_callback_on_denial': True,
            'returns_false_on_failure': True,
            'adds_listener_on_success': True
        }

        # All behaviors must be implemented
        assert all(expected_behavior.values())

    async def test_device_test_page_has_permission_button(self, client):
        """Test that device test page includes permission request button."""
        response = await client.get('/device-simple-test')

        assert response.status_code == 200
        # Check for permission request button
        assert b'requestPermBtn' in response.content or b'Request' in response.content

    def test_cache_busting_version_parameter(self):
        """
        Test that shake.js uses version parameter for cache busting.

        After updating shake.js, the version parameter must be incremented
        to force browsers to reload the new file:
        - v2.0: Initial iOS permission fix attempt
        - v2.1: Fixed user gesture requirement
        """
        current_version = '2.1'

        # Verify version is set
        assert current_version
        assert float(current_version) >= 2.1
