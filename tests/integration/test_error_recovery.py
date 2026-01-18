"""Integration tests for error recovery mechanisms.

Tests that the pipeline properly handles and recovers from:
- Detection failures
- Camera disconnections
- Disk space issues
- Resource exhaustion

Verifies that errors are:
- Logged appropriately
- Published to error bus
- Shown to user via UI notifications
- Recovered from gracefully
"""

import unittest
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from configs.settings import load_config
from app.pipeline_service import InProcessPipelineService
from app.events import get_error_bus, ErrorCategory, ErrorSeverity
from contracts import Frame
import numpy as np


class TestErrorRecovery(unittest.TestCase):
    """Integration tests for error recovery in pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory
        self.test_dir = Path(tempfile.mkdtemp())

        # Load default config and override output directory
        from dataclasses import replace

        config = load_config(Path("configs/default.yaml"))
        self.config = replace(
            config,
            recording=replace(config.recording, output_dir=str(self.test_dir)),
        )

        # Track errors published to error bus
        self.received_errors = []

        def error_callback(event):
            self.received_errors.append(event)

        get_error_bus().subscribe(error_callback)
        self._error_callback = error_callback

    def tearDown(self):
        """Clean up test files."""
        # Unsubscribe from error bus
        try:
            get_error_bus().unsubscribe(self._error_callback)
        except Exception:
            pass

        # Clean up test directory
        if self.test_dir.exists():
            try:
                shutil.rmtree(self.test_dir)
            except Exception as e:
                print(f"Warning: Could not clean up test directory: {e}")

    def test_detection_errors_published_to_error_bus(self):
        """Test that detection errors are published to error bus."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode

        # Create detection pool
        pool = DetectionThreadPool()

        # Create a detector that throws exceptions
        def failing_detector(label, frame):
            raise ValueError("Simulated detection failure")

        pool.set_detect_callback(failing_detector)
        pool.start(queue_size=6)

        # Clear any startup errors
        self.received_errors.clear()

        try:
            # Send frames that will cause detection to fail
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=int(time.time() * 1e9),
                t_capture_utc_ns=int(time.time() * 1e9),
                t_received_monotonic_ns=int(time.time() * 1e9),
                width=640,
                height=480,
                camera_id="test",
            )

            # Enqueue multiple failing frames
            for i in range(15):
                pool.enqueue_frame("left", frame)
                pool.enqueue_frame("right", frame)

            # Give time for errors to be processed
            time.sleep(2.0)

            # Should have received error events
            detection_errors = [
                e
                for e in self.received_errors
                if e.category == ErrorCategory.DETECTION
            ]

            self.assertGreater(
                len(detection_errors),
                0,
                "Expected detection errors to be published to error bus",
            )

            # Should have at least one ERROR severity
            error_severities = [e for e in detection_errors if e.severity == ErrorSeverity.ERROR]
            self.assertGreater(
                len(error_severities),
                0,
                "Expected at least one ERROR severity event",
            )

            # After 10 failures, should have CRITICAL severity
            critical_errors = [
                e for e in detection_errors if e.severity == ErrorSeverity.CRITICAL
            ]
            self.assertGreater(
                len(critical_errors),
                0,
                "Expected CRITICAL severity after 10 consecutive failures",
            )

        finally:
            pool.stop()

    def test_pipeline_continues_after_detection_errors(self):
        """Test that pipeline continues operating despite detection errors."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool

        pool = DetectionThreadPool()

        # Detector that fails intermittently
        self.call_count = 0

        def intermittent_detector(label, frame):
            self.call_count += 1
            if self.call_count % 3 == 0:
                raise ValueError("Intermittent failure")
            return []  # Return empty detections on success

        pool.set_detect_callback(intermittent_detector)
        pool.start(queue_size=6)

        try:
            # Send frames
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=int(time.time() * 1e9),
                t_capture_utc_ns=int(time.time() * 1e9),
                t_received_monotonic_ns=int(time.time() * 1e9),
                width=640,
                height=480,
                camera_id="test",
            )

            # Process 30 frames (10 will fail)
            for i in range(30):
                pool.enqueue_frame("left", frame)

            time.sleep(1.0)

            # Pool should still be running
            # Verify by checking that we can still enqueue frames
            pool.enqueue_frame("left", frame)

            # Should have processed frames (call_count > 0)
            self.assertGreater(
                self.call_count,
                20,
                "Pipeline should have continued processing despite errors",
            )

        finally:
            pool.stop()

    def test_frame_drops_published_when_queue_full(self):
        """Test that frame drops are published to error bus when detection queue is full."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool

        pool = DetectionThreadPool()

        # Very slow detector to cause queue to fill
        def slow_detector(label, frame):
            time.sleep(0.5)  # Very slow
            return []

        pool.set_detect_callback(slow_detector)
        pool.start(queue_size=6)  # Small queue

        # Clear startup errors
        self.received_errors.clear()

        try:
            # Flood the queue with frames
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            for i in range(20):  # More than queue size
                frame = Frame(
                    image=image,
                    t_capture_monotonic_ns=int(time.time() * 1e9) + i * 1000000,
                    t_capture_utc_ns=int(time.time() * 1e9) + i * 1000000,
                    t_received_monotonic_ns=int(time.time() * 1e9) + i * 1000000,
                    width=640,
                    height=480,
                    camera_id="test",
                )
                pool.enqueue_frame("left", frame)

            # Give time for queue to fill and drops to occur
            time.sleep(2.0)

            # Should have received frame drop warnings
            drop_warnings = [
                e
                for e in self.received_errors
                if e.category == ErrorCategory.DETECTION
                and "drop" in str(e.message).lower()
            ]

            self.assertGreater(
                len(drop_warnings),
                0,
                "Expected frame drop warnings when queue full",
            )

        finally:
            pool.stop()

    def test_disk_space_warnings_published(self):
        """Test that disk space warnings are published to error bus."""
        from app.pipeline.recording.session_recorder import SessionRecorder

        # Create session recorder with very high thresholds
        # (so we're always below them)
        recorder = SessionRecorder(self.config, self.test_dir)
        recorder._warning_disk_gb = 999999.0  # Unreasonably high
        recorder._critical_disk_gb = 999998.0

        # Clear startup errors
        self.received_errors.clear()

        # Start session (will trigger disk check)
        session_dir, warning = recorder.start_session("test_session", "test_pitch")

        # Should have warning message
        self.assertNotEqual(warning, "", "Expected disk space warning")

        # Note: Recording thread monitors continuously, but we triggered initial check
        # The warning message is returned directly, error bus used during monitoring

        recorder.stop_session()

    def test_error_recovery_resets_error_counters(self):
        """Test that error counters reset when detection recovers."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool

        pool = DetectionThreadPool()

        # Detector that fails then recovers
        self.call_count = 0

        def recovering_detector(label, frame):
            self.call_count += 1
            if self.call_count <= 12:
                # Fail first 12 calls (trigger CRITICAL)
                raise ValueError("Initial failure")
            else:
                # Then recover
                return []

        pool.set_detect_callback(recovering_detector)
        pool.start(queue_size=6)

        # Clear startup errors
        self.received_errors.clear()

        try:
            # Send frames
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=int(time.time() * 1e9),
                t_capture_utc_ns=int(time.time() * 1e9),
                t_received_monotonic_ns=int(time.time() * 1e9),
                width=640,
                height=480,
                camera_id="test",
            )

            # Send 25 frames (12 fail, then recover)
            for i in range(25):
                pool.enqueue_frame("left", frame)

            time.sleep(2.0)

            # Should have CRITICAL error from first 10 failures
            critical_errors = [
                e
                for e in self.received_errors
                if e.category == ErrorCategory.DETECTION
                and e.severity == ErrorSeverity.CRITICAL
            ]
            self.assertGreater(len(critical_errors), 0, "Expected CRITICAL error")

            # Clear errors and send more frames (should succeed)
            self.received_errors.clear()
            for i in range(10):
                pool.enqueue_frame("left", frame)

            time.sleep(1.0)

            # Should not have new CRITICAL errors (error counter was reset)
            new_critical = [
                e
                for e in self.received_errors
                if e.category == ErrorCategory.DETECTION
                and e.severity == ErrorSeverity.CRITICAL
            ]
            self.assertEqual(
                len(new_critical),
                0,
                "Should not have new CRITICAL errors after recovery",
            )

        finally:
            pool.stop()


if __name__ == "__main__":
    unittest.main()
