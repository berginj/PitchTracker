"""Unit tests for video codec fallback logic (Phase 1 Fix #3)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import cv2

from app.pipeline.recording.session_recorder import SessionRecorder


class TestCodecFallback(unittest.TestCase):
    """Test video codec fallback improvements."""

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
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_first_codec_success(self, mock_fourcc, mock_writer_class):
        """Test that first codec (MJPG) is used if available."""

        # Mock successful writer
        mock_writer = Mock()
        mock_writer.isOpened.return_value = True
        mock_writer_class.return_value = mock_writer

        # Open writer
        path = self.temp_dir / "test.avi"
        writer = self.recorder._open_video_writer(path, 640, 480, 30)

        # Should return the writer
        self.assertEqual(writer, mock_writer)

        # Should only try MJPG (first codec)
        mock_fourcc.assert_called_once_with(*"MJPG")
        mock_writer_class.assert_called_once()

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_fallback_to_second_codec(self, mock_fourcc, mock_writer_class):
        """Test fallback to XVID if MJPG fails."""

        # First writer fails, second succeeds
        failed_writer = Mock()
        failed_writer.isOpened.return_value = False

        success_writer = Mock()
        success_writer.isOpened.return_value = True

        mock_writer_class.side_effect = [failed_writer, success_writer]

        # Open writer
        path = self.temp_dir / "test.avi"
        with self.assertLogs(level='DEBUG') as log_context:
            writer = self.recorder._open_video_writer(path, 640, 480, 30)

        # Should return second writer
        self.assertEqual(writer, success_writer)

        # Should try MJPG then XVID
        self.assertEqual(mock_fourcc.call_count, 2)
        mock_fourcc.assert_any_call(*"MJPG")
        mock_fourcc.assert_any_call(*"XVID")

        # Should release failed writer
        failed_writer.release.assert_called_once()

        # Should log fallback attempt
        self.assertTrue(any("Codec MJPG failed" in msg for msg in log_context.output))

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_all_codecs_fail(self, mock_fourcc, mock_writer_class):
        """Test that RuntimeError is raised if all codecs fail."""

        # All writers fail
        failed_writer = Mock()
        failed_writer.isOpened.return_value = False
        mock_writer_class.return_value = failed_writer

        # Should raise RuntimeError
        path = self.temp_dir / "test.avi"
        with self.assertRaises(RuntimeError) as context:
            self.recorder._open_video_writer(path, 640, 480, 30)

        # Error message should list attempted codecs
        self.assertIn("MJPG", str(context.exception))
        self.assertIn("XVID", str(context.exception))
        self.assertIn("H264", str(context.exception))
        self.assertIn("MP4V", str(context.exception))

        # Should have tried all 4 codecs
        self.assertEqual(mock_writer_class.call_count, 4)

        # Should have released all failed writers
        self.assertEqual(failed_writer.release.call_count, 4)

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_both_cameras_use_same_codec_sequence(self, mock_fourcc, mock_writer_class):
        """Test that both left and right cameras use same fallback sequence."""

        # MJPG fails, XVID succeeds
        def writer_side_effect(*args, **kwargs):
            writer = Mock()
            # First call (MJPG) fails, second call (XVID) succeeds
            if mock_writer_class.call_count == 1 or mock_writer_class.call_count == 3:
                writer.isOpened.return_value = False
            else:
                writer.isOpened.return_value = True
            return writer

        mock_writer_class.side_effect = writer_side_effect

        # Create session directory
        self.recorder._session_dir = self.temp_dir / "session"
        self.recorder._session_dir.mkdir()

        # Mock CSV file creation
        with patch.object(Path, 'open', create=True) as mock_open:
            mock_open.return_value = Mock()

            with patch('csv.writer', return_value=Mock()):
                self.recorder._open_writers()

        # Both cameras should have tried MJPG first, then XVID
        # Total calls: 2 cameras × 2 codecs = 4
        self.assertEqual(mock_writer_class.call_count, 4)

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_left_writer_cleaned_up_if_right_fails(self, mock_fourcc, mock_writer_class):
        """Test that left writer is cleaned up if right writer fails."""

        call_count = [0]

        def writer_side_effect(*args, **kwargs):
            call_count[0] += 1
            writer = Mock()

            # First video writer (left camera) succeeds on first codec
            if call_count[0] == 1:
                writer.isOpened.return_value = True
                return writer

            # Second video writer (right camera) - all codecs fail
            writer.isOpened.return_value = False
            return writer

        mock_writer_class.side_effect = writer_side_effect

        # Create session directory
        self.recorder._session_dir = self.temp_dir / "session"
        self.recorder._session_dir.mkdir()

        # Mock CSV file creation
        with patch.object(Path, 'open', create=True):
            with patch('csv.writer'):
                # Should raise RuntimeError
                with self.assertRaises(RuntimeError):
                    self.recorder._open_writers()

        # Left writer should have been cleaned up
        self.assertIsNone(self.recorder._left_writer)
        self.assertIsNone(self.recorder._right_writer)

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_codec_success_logged(self, mock_fourcc, mock_writer_class):
        """Test that successful codec is logged."""

        # MJPG fails, XVID succeeds
        failed_writer = Mock()
        failed_writer.isOpened.return_value = False

        success_writer = Mock()
        success_writer.isOpened.return_value = True

        mock_writer_class.side_effect = [failed_writer, success_writer]

        # Open writer
        path = self.temp_dir / "test.avi"
        with self.assertLogs(level='INFO') as log_context:
            self.recorder._open_video_writer(path, 640, 480, 30)

        # Should log successful codec
        self.assertTrue(any("Video writer opened successfully" in msg for msg in log_context.output))
        self.assertTrue(any("XVID" in msg for msg in log_context.output))

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_writer_receives_correct_parameters(self, mock_fourcc, mock_writer_class):
        """Test that VideoWriter receives correct parameters."""

        mock_writer = Mock()
        mock_writer.isOpened.return_value = True
        mock_writer_class.return_value = mock_writer

        mock_fourcc.return_value = 12345  # Mock fourcc value

        # Open writer
        path = self.temp_dir / "test.avi"
        self.recorder._open_video_writer(path, 1920, 1080, 60)

        # Check VideoWriter was called with correct params
        mock_writer_class.assert_called_with(
            str(path),
            12345,  # fourcc
            60.0,   # fps as float
            (1920, 1080),  # size
            True    # isColor
        )

    @patch('cv2.VideoWriter')
    @patch('cv2.VideoWriter_fourcc')
    def test_release_called_on_failed_writers(self, mock_fourcc, mock_writer_class):
        """Test that release() is called on all failed writers."""

        # Create multiple failed writers
        failed_writers = []
        for _ in range(3):
            writer = Mock()
            writer.isOpened.return_value = False
            failed_writers.append(writer)

        # Last one succeeds
        success_writer = Mock()
        success_writer.isOpened.return_value = True

        mock_writer_class.side_effect = failed_writers + [success_writer]

        # Open writer
        path = self.temp_dir / "test.avi"
        self.recorder._open_video_writer(path, 640, 480, 30)

        # All failed writers should have release() called
        for writer in failed_writers:
            writer.release.assert_called_once()

        # Success writer should NOT have release() called
        success_writer.release.assert_not_called()


if __name__ == '__main__':
    unittest.main()
