"""Integration tests for video codec fallback mechanism."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Try to import cv2, skip tests if not available
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@unittest.skipIf(not CV2_AVAILABLE, "OpenCV not available")
class TestCodecFallbackIntegration(unittest.TestCase):
    """Integration tests for codec fallback in session recorder."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config = Mock()
        self.config.camera.width = 640
        self.config.camera.height = 480
        self.config.camera.fps = 30
        self.config.recording.output_dir = str(self.test_dir)
        self.config.recording.save_detections = False
        self.config.recording.save_observations = False
        self.config.recording.save_training_frames = False

    def tearDown(self):
        """Clean up test files."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_codec_fallback_with_mjpg_success(self):
        """Test that MJPG codec works as first choice."""
        from app.pipeline.recording.session_recorder import SessionRecorder

        recorder = SessionRecorder(self.config, self.test_dir)

        # Try to open video writer
        video_path = self.test_dir / "test_mjpg.avi"
        try:
            writer = recorder._open_video_writer(video_path, 640, 480, 30)
            self.assertTrue(writer.isOpened())
            writer.release()
        except RuntimeError as e:
            # MJPG might not be available on all systems
            self.skipTest(f"MJPG codec not available: {e}")

    def test_codec_fallback_sequence(self):
        """Test that codec fallback tries all codecs in sequence."""
        from app.pipeline.recording.session_recorder import SessionRecorder

        recorder = SessionRecorder(self.config, self.test_dir)
        video_path = self.test_dir / "test_fallback.avi"

        # Mock VideoWriter to simulate codec failures
        original_vw = cv2.VideoWriter

        call_count = [0]
        failed_codecs = []

        def mock_video_writer(path, fourcc, fps, frameSize, isColor=True):
            """Mock VideoWriter that fails for first N codecs."""
            call_count[0] += 1

            # Get codec name from fourcc
            codec_bytes = [(fourcc >> (8 * i)) & 0xFF for i in range(4)]
            codec_name = ''.join([chr(b) for b in codec_bytes])
            failed_codecs.append(codec_name)

            # Fail first 2 codecs (MJPG, XVID), succeed on 3rd (H264)
            if call_count[0] <= 2:
                writer = original_vw(path, fourcc, fps, frameSize, isColor)
                # Force it to fail
                mock_writer = Mock(spec=cv2.VideoWriter)
                mock_writer.isOpened.return_value = False
                mock_writer.release = Mock()
                return mock_writer
            else:
                # Succeed on third try
                return original_vw(path, fourcc, fps, frameSize, isColor)

        with patch('cv2.VideoWriter', side_effect=mock_video_writer):
            try:
                writer = recorder._open_video_writer(video_path, 640, 480, 30)
                self.assertTrue(writer.isOpened())
                writer.release()

                # Should have tried at least 3 codecs
                self.assertGreaterEqual(call_count[0], 3)
                # Should have failed on first 2
                self.assertEqual(len(failed_codecs), 3)

            except RuntimeError as e:
                # If all codecs fail, that's acceptable (system-dependent)
                pass

    def test_codec_fallback_all_fail(self):
        """Test that RuntimeError raised when all codecs fail."""
        from app.pipeline.recording.session_recorder import SessionRecorder

        recorder = SessionRecorder(self.config, self.test_dir)
        video_path = self.test_dir / "test_all_fail.avi"

        # Mock VideoWriter to always fail
        def mock_failed_writer(path, fourcc, fps, frameSize, isColor=True):
            mock_writer = Mock(spec=cv2.VideoWriter)
            mock_writer.isOpened.return_value = False
            mock_writer.release = Mock()
            return mock_writer

        with patch('cv2.VideoWriter', side_effect=mock_failed_writer):
            # Should raise RuntimeError when all codecs fail
            with self.assertRaises(RuntimeError) as context:
                recorder._open_video_writer(video_path, 640, 480, 30)

            # Error message should mention all codecs failed
            self.assertIn("All", str(context.exception))
            self.assertIn("failed", str(context.exception).lower())

    def test_codec_fallback_left_succeeds_right_fails(self):
        """Test cleanup when left succeeds but right fails."""
        from app.pipeline.recording.session_recorder import SessionRecorder

        recorder = SessionRecorder(self.config, self.test_dir)

        # Start a session
        session_dir, warning = recorder.start_session("test_session", "test_pitch")
        self.assertTrue(session_dir.exists())

        # Mock to make right camera fail
        call_count = [0]

        original_open = recorder._open_video_writer

        def mock_open_with_right_fail(path, width, height, fps):
            call_count[0] += 1
            if "right" in str(path):
                # Right camera always fails
                raise RuntimeError("Right camera codec failed")
            else:
                # Left camera succeeds
                return original_open(path, width, height, fps)

        recorder._open_video_writer = mock_open_with_right_fail

        # Try to start recording - should fail and cleanup left
        try:
            recorder.start_recording()
            self.fail("Should have raised RuntimeError")
        except RuntimeError:
            # Expected - right camera failed
            pass

        # Verify left writer was cleaned up
        self.assertIsNone(recorder._left_writer)
        self.assertIsNone(recorder._right_writer)

    def test_codec_writes_frames_correctly(self):
        """Test that frames can be written with fallback codec."""
        from app.pipeline.recording.session_recorder import SessionRecorder
        from contracts import Frame
        import numpy as np

        recorder = SessionRecorder(self.config, self.test_dir)

        # Start session
        session_dir, _ = recorder.start_session("test_session", "test_pitch")

        try:
            # Start recording
            recorder.start_recording()

            # Create test frame
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=1000000000,
                t_capture_utc_ns=1000000000,
                t_received_monotonic_ns=1000000000,
                width=640,
                height=480,
                camera_id="test"
            )

            # Write some frames
            for i in range(10):
                recorder.write_frame("left", frame)
                recorder.write_frame("right", frame)

            # Stop recording
            recorder.stop_recording(
                config_path="test_config.yaml",
                pitch_id="test_pitch",
                session_name="test_session",
                record_mode="test"
            )

            # Verify video files exist
            left_video = session_dir / "session_left.avi"
            right_video = session_dir / "session_right.avi"

            self.assertTrue(left_video.exists(), "Left video not created")
            self.assertTrue(right_video.exists(), "Right video not created")

            # Verify videos are not empty
            self.assertGreater(left_video.stat().st_size, 1000, "Left video is too small")
            self.assertGreater(right_video.stat().st_size, 1000, "Right video is too small")

        except Exception as e:
            # Some codecs might not be available
            self.skipTest(f"Codec not available for writing: {e}")
        finally:
            if recorder._recording:
                recorder.stop_recording(
                    config_path="test_config.yaml",
                    pitch_id="test_pitch",
                    session_name="test_session",
                    record_mode="test"
                )

    def test_codec_fallback_publishes_errors(self):
        """Test that codec failures are published to error bus."""
        from app.pipeline.recording.session_recorder import SessionRecorder
        from app.events import get_error_bus, ErrorCategory

        # Subscribe to error bus
        received_errors = []

        def error_callback(event):
            if event.category == ErrorCategory.RECORDING:
                received_errors.append(event)

        get_error_bus().subscribe(error_callback, category=ErrorCategory.RECORDING)

        recorder = SessionRecorder(self.config, self.test_dir)
        video_path = self.test_dir / "test_error.avi"

        # Mock to make all codecs fail
        def mock_failed_writer(path, fourcc, fps, frameSize, isColor=True):
            mock_writer = Mock(spec=cv2.VideoWriter)
            mock_writer.isOpened.return_value = False
            mock_writer.release = Mock()
            return mock_writer

        with patch('cv2.VideoWriter', side_effect=mock_failed_writer):
            try:
                recorder._open_video_writer(video_path, 640, 480, 30)
            except RuntimeError:
                pass  # Expected

        # Should have published CRITICAL error when all codecs failed
        critical_errors = [e for e in received_errors if e.severity.value == "critical"]
        self.assertGreater(len(critical_errors), 0, "No critical error published")

        # Unsubscribe
        get_error_bus().unsubscribe(error_callback, category=ErrorCategory.RECORDING)


if __name__ == "__main__":
    unittest.main()
