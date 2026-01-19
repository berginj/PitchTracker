"""Tests for camera reconnection functionality."""

import unittest
import threading
import time
from unittest.mock import Mock, MagicMock, patch

from app.camera import CameraReconnectionManager, CameraState


class TestCameraReconnectionManager(unittest.TestCase):
    """Test suite for CameraReconnectionManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.mgr = CameraReconnectionManager(
            max_reconnect_attempts=3,
            base_delay=0.1,  # Short delays for testing
            max_delay=1.0
        )

    def tearDown(self):
        """Clean up after tests."""
        # Unregister all cameras to stop threads
        for camera_id in list(self.mgr._camera_states.keys()):
            self.mgr.unregister_camera(camera_id)

        # Wait for threads to finish
        time.sleep(0.2)

    def test_register_camera(self):
        """Test registering a camera for monitoring."""
        self.mgr.register_camera("left")

        self.assertEqual(self.mgr.get_camera_state("left"), CameraState.CONNECTED)
        self.assertEqual(self.mgr._reconnect_attempts["left"], 0)

    def test_unregister_camera(self):
        """Test unregistering a camera."""
        self.mgr.register_camera("left")
        self.mgr.unregister_camera("left")

        self.assertIsNone(self.mgr.get_camera_state("left"))
        self.assertNotIn("left", self.mgr._reconnect_attempts)

    def test_report_disconnection(self):
        """Test reporting camera disconnection."""
        self.mgr.register_camera("left")

        # Mock reconnect callback to prevent actual reconnection
        self.mgr.set_reconnect_callback(lambda camera_id: False)

        # Report disconnection
        self.mgr.report_disconnection("left")

        # Wait for state change
        time.sleep(0.05)

        # Should be in DISCONNECTED or RECONNECTING state
        state = self.mgr.get_camera_state("left")
        self.assertIn(state, [CameraState.DISCONNECTED, CameraState.RECONNECTING])

    def test_successful_reconnection(self):
        """Test successful camera reconnection."""
        self.mgr.register_camera("left")

        # Mock successful reconnection
        reconnect_called = threading.Event()
        def mock_reconnect(camera_id):
            reconnect_called.set()
            return True

        self.mgr.set_reconnect_callback(mock_reconnect)

        # Report disconnection
        self.mgr.report_disconnection("left")

        # Wait for reconnection attempt
        reconnect_called.wait(timeout=2.0)
        time.sleep(0.2)  # Allow state update

        # Should be back to CONNECTED
        self.assertEqual(self.mgr.get_camera_state("left"), CameraState.CONNECTED)
        self.assertEqual(self.mgr._reconnect_attempts["left"], 0)

    def test_failed_reconnection(self):
        """Test camera reconnection failure after max attempts."""
        self.mgr.register_camera("left")

        # Mock failed reconnection
        attempts = []
        def mock_reconnect(camera_id):
            attempts.append(camera_id)
            return False

        self.mgr.set_reconnect_callback(mock_reconnect)

        # Report disconnection
        self.mgr.report_disconnection("left")

        # Wait for all attempts to complete
        time.sleep(3.0)  # Max 3 attempts with short delays

        # Should have tried max_reconnect_attempts times
        self.assertEqual(len(attempts), 3)

        # Should be in FAILED state
        self.assertEqual(self.mgr.get_camera_state("left"), CameraState.FAILED)

    def test_state_change_callback(self):
        """Test state change callback is invoked."""
        self.mgr.register_camera("left")

        # Track state changes
        state_changes = []
        def on_state_change(camera_id, state):
            state_changes.append((camera_id, state))

        self.mgr.set_state_change_callback(on_state_change)

        # Mock reconnect callback
        self.mgr.set_reconnect_callback(lambda camera_id: False)

        # Report disconnection
        self.mgr.report_disconnection("left")

        # Wait for state changes
        time.sleep(0.3)

        # Should have at least DISCONNECTED and RECONNECTING states
        self.assertGreaterEqual(len(state_changes), 1)
        self.assertEqual(state_changes[0][0], "left")
        self.assertIn(state_changes[0][1], [CameraState.DISCONNECTED, CameraState.RECONNECTING])

    def test_report_connection_success(self):
        """Test reporting successful connection."""
        self.mgr.register_camera("left")

        # Simulate disconnection
        self.mgr._camera_states["left"] = CameraState.DISCONNECTED
        self.mgr._reconnect_attempts["left"] = 2

        # Report connection success
        self.mgr.report_connection_success("left")

        # Should be CONNECTED with reset attempts
        self.assertEqual(self.mgr.get_camera_state("left"), CameraState.CONNECTED)
        self.assertEqual(self.mgr._reconnect_attempts["left"], 0)

    def test_multiple_cameras(self):
        """Test managing multiple cameras simultaneously."""
        self.mgr.register_camera("left")
        self.mgr.register_camera("right")

        self.assertEqual(self.mgr.get_camera_state("left"), CameraState.CONNECTED)
        self.assertEqual(self.mgr.get_camera_state("right"), CameraState.CONNECTED)

        # Mock reconnection
        self.mgr.set_reconnect_callback(lambda camera_id: False)

        # Disconnect both
        self.mgr.report_disconnection("left")
        self.mgr.report_disconnection("right")

        time.sleep(0.2)

        # Both should be disconnected/reconnecting
        left_state = self.mgr.get_camera_state("left")
        right_state = self.mgr.get_camera_state("right")

        self.assertIn(left_state, [CameraState.DISCONNECTED, CameraState.RECONNECTING, CameraState.FAILED])
        self.assertIn(right_state, [CameraState.DISCONNECTED, CameraState.RECONNECTING, CameraState.FAILED])

    def test_exponential_backoff_delays(self):
        """Test that reconnection delays follow exponential backoff."""
        self.mgr.register_camera("left")

        # Track attempt times
        attempt_times = []
        def mock_reconnect(camera_id):
            attempt_times.append(time.time())
            return False

        self.mgr.set_reconnect_callback(mock_reconnect)

        # Report disconnection
        self.mgr.report_disconnection("left")

        # Wait for attempts
        time.sleep(3.0)

        # Should have 3 attempts
        self.assertEqual(len(attempt_times), 3)

        # Check delays increase (approximately)
        if len(attempt_times) >= 2:
            delay1 = attempt_times[1] - attempt_times[0]
            delay2 = attempt_times[2] - attempt_times[1] if len(attempt_times) >= 3 else 0

            # Delays should increase (allowing for timing variance)
            self.assertGreater(delay2, delay1 * 0.8)  # Allow 20% variance

    def test_thread_cleanup_on_unregister(self):
        """Test that reconnection threads are cleaned up on unregister."""
        self.mgr.register_camera("left")

        # Mock reconnection to keep thread alive
        self.mgr.set_reconnect_callback(lambda camera_id: False)

        # Start reconnection
        self.mgr.report_disconnection("left")
        time.sleep(0.1)

        # Should have active thread
        self.assertIn("left", self.mgr._reconnect_threads)

        # Unregister camera
        self.mgr.unregister_camera("left")

        # Wait for thread cleanup
        time.sleep(0.2)

        # Thread should be cleaned up
        self.assertNotIn("left", self.mgr._reconnect_threads)


if __name__ == "__main__":
    unittest.main()
