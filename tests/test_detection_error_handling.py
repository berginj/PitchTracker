"""Unit tests for detection thread error handling (Phase 1 Fix #1)."""

import queue
import time
import unittest
from unittest.mock import Mock, patch

from app.pipeline.detection.threading_pool import DetectionThreadPool
from contracts import Detection, Frame


class TestDetectionErrorHandling(unittest.TestCase):
    """Test detection thread error handling improvements."""

    def setUp(self):
        """Set up test fixtures."""
        self.pool = DetectionThreadPool(mode="per_camera", worker_count=2)

    def tearDown(self):
        """Clean up after tests."""
        if self.pool.is_running():
            self.pool.stop()

    def test_detection_callback_exception_is_logged(self):
        """Test that exceptions in detection callback are logged, not swallowed."""

        def failing_detector(label: str, frame: Frame):
            raise RuntimeError("Simulated detection failure")

        self.pool.set_detect_callback(failing_detector)

        # Create mock frame
        frame = Mock(spec=Frame)
        frame.frame_index = 1
        frame.camera_id = "test"

        # Should log error but not crash
        with self.assertLogs(level='ERROR') as log_context:
            detections = self.pool._detect_frame("left", frame)

        # Should return empty list
        self.assertEqual(detections, [])

        # Should have logged the error
        self.assertTrue(any("Detection failed" in msg for msg in log_context.output))
        self.assertTrue(any("RuntimeError" in msg for msg in log_context.output))

    def test_error_counter_increments(self):
        """Test that error counter increments on failures."""

        def failing_detector(label: str, frame: Frame):
            raise ValueError("Test error")

        self.pool.set_detect_callback(failing_detector)
        frame = Mock(spec=Frame)

        # Call multiple times
        for _ in range(5):
            self.pool._detect_frame("left", frame)

        # Check error stats
        stats = self.pool.get_error_stats()
        self.assertEqual(stats["left"], 5)
        self.assertEqual(stats["right"], 0)

    def test_error_counter_resets_on_success(self):
        """Test that error counter resets when detection succeeds."""

        call_count = [0]

        def intermittent_detector(label: str, frame: Frame):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise RuntimeError("Fail first 3 times")
            return []  # Success

        self.pool.set_detect_callback(intermittent_detector)
        frame = Mock(spec=Frame)

        # Fail 3 times
        for _ in range(3):
            self.pool._detect_frame("left", frame)

        stats = self.pool.get_error_stats()
        self.assertEqual(stats["left"], 3)

        # Succeed once
        with self.assertLogs(level='INFO') as log_context:
            self.pool._detect_frame("left", frame)

        # Counter should reset
        stats = self.pool.get_error_stats()
        self.assertEqual(stats["left"], 0)

        # Should log recovery message
        self.assertTrue(any("Detection recovered" in msg for msg in log_context.output))

    def test_error_callback_invoked_after_threshold(self):
        """Test that error callback is invoked after max consecutive errors."""

        error_callback = Mock()
        self.pool.set_error_callback(error_callback)

        def failing_detector(label: str, frame: Frame):
            raise RuntimeError("Persistent failure")

        self.pool.set_detect_callback(failing_detector)
        frame = Mock(spec=Frame)

        # Fail 9 times - should not trigger callback
        for _ in range(9):
            self.pool._detect_frame("left", frame)

        error_callback.assert_not_called()

        # 10th failure should trigger callback
        with self.assertLogs(level='CRITICAL'):
            self.pool._detect_frame("left", frame)

        error_callback.assert_called_once()
        call_args = error_callback.call_args[0]
        self.assertEqual(call_args[0], "detection_left")
        self.assertIsInstance(call_args[1], RuntimeError)

    def test_error_logging_throttled(self):
        """Test that error logging is throttled to avoid spam."""

        def failing_detector(label: str, frame: Frame):
            raise RuntimeError("Test error")

        self.pool.set_detect_callback(failing_detector)
        frame = Mock(spec=Frame)

        # Call many times in quick succession
        with self.assertLogs(level='ERROR') as log_context:
            for _ in range(10):
                self.pool._detect_frame("left", frame)
                time.sleep(0.1)  # 100ms between calls

        # Should only log once (throttled to 5 seconds)
        error_logs = [msg for msg in log_context.output if "Detection failed" in msg]
        self.assertEqual(len(error_logs), 1)

    def test_error_stats_per_camera(self):
        """Test that errors are tracked separately per camera."""

        def failing_detector(label: str, frame: Frame):
            raise RuntimeError("Test error")

        self.pool.set_detect_callback(failing_detector)
        frame = Mock(spec=Frame)

        # Fail left camera 3 times
        for _ in range(3):
            self.pool._detect_frame("left", frame)

        # Fail right camera 5 times
        for _ in range(5):
            self.pool._detect_frame("right", frame)

        # Check stats
        stats = self.pool.get_error_stats()
        self.assertEqual(stats["left"], 3)
        self.assertEqual(stats["right"], 5)

    def test_error_callback_exception_does_not_crash(self):
        """Test that exception in error callback doesn't crash detection."""

        def crashing_error_callback(source: str, exception: Exception):
            raise ValueError("Error callback failed!")

        self.pool.set_error_callback(crashing_error_callback)

        def failing_detector(label: str, frame: Frame):
            raise RuntimeError("Detection error")

        self.pool.set_detect_callback(failing_detector)
        frame = Mock(spec=Frame)

        # Trigger error callback (10+ failures)
        for _ in range(11):
            # Should not crash despite error callback failing
            detections = self.pool._detect_frame("left", frame)
            self.assertEqual(detections, [])

    def test_start_resets_error_counters(self):
        """Test that starting detection resets error counters."""

        def failing_detector(label: str, frame: Frame):
            raise RuntimeError("Test error")

        self.pool.set_detect_callback(failing_detector)
        frame = Mock(spec=Frame)

        # Accumulate errors
        for _ in range(5):
            self.pool._detect_frame("left", frame)

        stats = self.pool.get_error_stats()
        self.assertEqual(stats["left"], 5)

        # Start pool (resets counters)
        self.pool.start(queue_size=6)

        # Counters should be reset
        stats = self.pool.get_error_stats()
        self.assertEqual(stats["left"], 0)
        self.assertEqual(stats["right"], 0)

        self.pool.stop()


if __name__ == '__main__':
    unittest.main()
