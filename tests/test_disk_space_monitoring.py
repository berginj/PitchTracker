"""Unit tests for disk space monitoring (Phase 1 Fix #2)."""

import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.pipeline.recording.session_recorder import SessionRecorder


class TestDiskSpaceMonitoring(unittest.TestCase):
    """Test disk space monitoring improvements."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create mock config
        self.mock_config = Mock()
        self.mock_config.camera.width = 640
        self.mock_config.camera.height = 480
        self.mock_config.camera.fps = 30

        self.recorder = SessionRecorder(self.mock_config, self.temp_dir)

    def tearDown(self):
        """Clean up after tests."""
        # Stop monitoring if running
        self.recorder._monitoring_disk = False
        if self.recorder._disk_monitor_thread and self.recorder._disk_monitor_thread.is_alive():
            self.recorder._disk_monitor_thread.join(timeout=2.0)

        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('shutil.disk_usage')
    def test_critical_disk_space_triggers_callback(self, mock_disk_usage):
        """Test that critical disk space triggers emergency callback."""

        # Simulate 3GB free (below 5GB critical threshold)
        mock_usage = Mock()
        mock_usage.free = 3 * (1024**3)  # 3GB
        mock_disk_usage.return_value = mock_usage

        callback_called = []

        def disk_error_callback(free_gb, message):
            callback_called.append((free_gb, message))

        self.recorder.set_disk_error_callback(disk_error_callback)

        # Start monitoring in background
        self.recorder._monitoring_disk = True
        import threading
        monitor_thread = threading.Thread(target=self.recorder._monitor_disk_space)
        monitor_thread.start()

        # Wait for callback
        time.sleep(1.0)

        # Stop monitoring
        self.recorder._monitoring_disk = False
        monitor_thread.join(timeout=2.0)

        # Callback should have been called
        self.assertEqual(len(callback_called), 1)
        free_gb, message = callback_called[0]
        self.assertLess(free_gb, 5.0)
        self.assertIn("Critical", message)

    @patch('shutil.disk_usage')
    def test_warning_disk_space_logs_warning(self, mock_disk_usage):
        """Test that warning level disk space logs warnings."""

        # Simulate 15GB free (below 20GB warning, above 5GB critical)
        mock_usage = Mock()
        mock_usage.free = 15 * (1024**3)  # 15GB
        mock_disk_usage.return_value = mock_usage

        # Start monitoring
        self.recorder._monitoring_disk = True
        import threading
        monitor_thread = threading.Thread(target=self.recorder._monitor_disk_space)

        with self.assertLogs(level='WARNING') as log_context:
            monitor_thread.start()
            time.sleep(1.0)

        # Stop monitoring
        self.recorder._monitoring_disk = False
        monitor_thread.join(timeout=2.0)

        # Should have logged warning
        self.assertTrue(any("Low disk space" in msg for msg in log_context.output))
        self.assertTrue(any("15." in msg for msg in log_context.output))

    @patch('shutil.disk_usage')
    def test_sufficient_disk_space_no_warnings(self, mock_disk_usage):
        """Test that sufficient disk space doesn't trigger warnings."""

        # Simulate 100GB free (well above thresholds)
        mock_usage = Mock()
        mock_usage.free = 100 * (1024**3)  # 100GB
        mock_disk_usage.return_value = mock_usage

        callback_called = []

        def disk_error_callback(free_gb, message):
            callback_called.append((free_gb, message))

        self.recorder.set_disk_error_callback(disk_error_callback)

        # Start monitoring
        self.recorder._monitoring_disk = True
        import threading
        monitor_thread = threading.Thread(target=self.recorder._monitor_disk_space)
        monitor_thread.start()

        # Wait
        time.sleep(1.0)

        # Stop monitoring
        self.recorder._monitoring_disk = False
        monitor_thread.join(timeout=2.0)

        # No callback should have been called
        self.assertEqual(len(callback_called), 0)

    @patch('time.sleep')
    def test_monitoring_stops_on_flag_change(self, mock_sleep):
        """Test that monitoring thread stops when flag is set to False."""

        # Make sleep return immediately so loop iterates quickly
        mock_sleep.return_value = None

        # Start monitoring
        self.recorder._monitoring_disk = True
        import threading
        monitor_thread = threading.Thread(target=self.recorder._monitor_disk_space)
        monitor_thread.start()

        # Thread should be alive
        time.sleep(0.1)
        self.assertTrue(monitor_thread.is_alive())

        # Stop monitoring
        self.recorder._monitoring_disk = False
        monitor_thread.join(timeout=2.0)

        # Thread should be dead
        self.assertFalse(monitor_thread.is_alive())

    @patch('shutil.disk_usage')
    @patch('time.sleep')
    def test_warning_throttled_to_one_per_minute(self, mock_sleep, mock_disk_usage):
        """Test that warnings are throttled to once per minute."""

        # Simulate low disk space
        mock_usage = Mock()
        mock_usage.free = 15 * (1024**3)  # 15GB
        mock_disk_usage.return_value = mock_usage

        # Make sleep return immediately so loop iterates quickly
        mock_sleep.return_value = None

        # Start monitoring in background
        self.recorder._monitoring_disk = True
        import threading

        with self.assertLogs(level='WARNING') as log_context:
            monitor_thread = threading.Thread(target=self.recorder._monitor_disk_space)
            monitor_thread.start()

            # Let it run a few iterations (should log only once due to throttling)
            time.sleep(0.5)

            # Stop monitoring
            self.recorder._monitoring_disk = False
            monitor_thread.join(timeout=2.0)

        # Count warning messages - should only log once even with multiple iterations
        warning_count = sum(1 for msg in log_context.output if "Low disk space" in msg)
        self.assertEqual(warning_count, 1)

    @patch('shutil.disk_usage')
    def test_disk_error_callback_exception_handled(self, mock_disk_usage):
        """Test that exception in disk error callback doesn't crash monitoring."""

        # Simulate critical disk space
        mock_usage = Mock()
        mock_usage.free = 3 * (1024**3)  # 3GB
        mock_disk_usage.return_value = mock_usage

        def crashing_callback(free_gb, message):
            raise ValueError("Callback crashed!")

        self.recorder.set_disk_error_callback(crashing_callback)

        # Start monitoring - should not crash
        self.recorder._monitoring_disk = True
        import threading
        monitor_thread = threading.Thread(target=self.recorder._monitor_disk_space)

        with self.assertLogs(level='ERROR') as log_context:
            monitor_thread.start()
            time.sleep(1.0)

        # Stop monitoring
        self.recorder._monitoring_disk = False
        monitor_thread.join(timeout=2.0)

        # Should have logged the callback error
        self.assertTrue(any("Disk error callback failed" in msg for msg in log_context.output))

    @patch('shutil.disk_usage')
    def test_check_disk_space_at_session_start(self, mock_disk_usage):
        """Test that disk space is checked at session start."""

        # Simulate low disk space
        mock_usage = Mock()
        mock_usage.free = 30 * (1024**3)  # 30GB
        mock_disk_usage.return_value = mock_usage

        # Mock video writer to avoid actual file creation
        with patch('cv2.VideoWriter'):
            with patch.object(self.recorder, '_open_video_writer', return_value=Mock()):
                with self.assertLogs(level='INFO'):
                    session_dir, warning = self.recorder.start_session("test_session", "pitch-001")

        # Should return warning message since 30GB < 50GB recommended
        self.assertIn("Low disk space warning", warning)
        self.assertIn("30.0GB", warning)

    @patch('shutil.disk_usage')
    def test_monitoring_continues_after_exception(self, mock_disk_usage):
        """Test that monitoring continues even if disk_usage raises exception."""

        # First call raises exception, second succeeds
        mock_usage = Mock()
        mock_usage.free = 50 * (1024**3)
        mock_disk_usage.side_effect = [OSError("Disk error"), mock_usage]

        self.recorder._monitoring_disk = True
        import threading
        monitor_thread = threading.Thread(target=self.recorder._monitor_disk_space)

        with self.assertLogs(level='ERROR') as log_context:
            monitor_thread.start()
            time.sleep(6.0)  # Wait for 2 check cycles

        # Stop monitoring
        self.recorder._monitoring_disk = False
        monitor_thread.join(timeout=2.0)

        # Should have logged error
        self.assertTrue(any("Error monitoring disk space" in msg for msg in log_context.output))


if __name__ == '__main__':
    unittest.main()
