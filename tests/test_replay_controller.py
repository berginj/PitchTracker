"""Unit tests for ReplayController.

Tests the extracted ReplayController class from MainWindow refactoring.
Covers video replay, frame stepping, and detection visualization.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ui.controllers.replay_controller import ReplayController


class TestReplayControllerInit:
    """Tests for ReplayController initialization."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies for ReplayController."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.camera.pixfmt = "GRAY8"
        config.detector.filters.min_area = 10
        config.detector.filters.max_area = 1000
        config.detector.filters.min_circularity = 0.5
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0
        config.detector.frame_diff_threshold = 30
        config.detector.bg_diff_threshold = 40
        config.detector.bg_alpha = 0.01
        config.detector.edge_threshold = 100
        config.detector.blob_threshold = 127
        config.detector.runtime_budget_ms = 10
        config.detector.crop_padding_px = 20
        config.detector.min_consecutive = 2
        config.detector.mode = "MODE_A"

        return {
            "parent": Mock(),
            "left_view": Mock(),
            "right_view": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_lane_rect": Mock(return_value=None),
            "get_plate_rect": Mock(return_value=None),
            "get_active_rect": Mock(return_value=None),
            "stop_capture": Mock(),
            "start_timer": Mock(),
        }

    def test_initialization(self, mock_deps):
        """ReplayController should initialize with provided dependencies."""
        rc = ReplayController(**mock_deps)
        assert rc.is_active is False
        assert rc.is_paused is False

    def test_is_active_false_by_default(self, mock_deps):
        """is_active should be False when no replay is running."""
        rc = ReplayController(**mock_deps)
        assert rc.is_active is False

    def test_is_paused_false_by_default(self, mock_deps):
        """is_paused should be False by default."""
        rc = ReplayController(**mock_deps)
        assert rc.is_paused is False


class TestStartReplay:
    """Tests for starting video replay."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.camera.pixfmt = "GRAY8"
        config.detector.filters.min_area = 10
        config.detector.filters.max_area = 1000
        config.detector.filters.min_circularity = 0.5
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0
        config.detector.frame_diff_threshold = 30
        config.detector.bg_diff_threshold = 40
        config.detector.bg_alpha = 0.01
        config.detector.edge_threshold = 100
        config.detector.blob_threshold = 127
        config.detector.runtime_budget_ms = 10
        config.detector.crop_padding_px = 20
        config.detector.min_consecutive = 2
        config.detector.mode = "MODE_A"

        return {
            "parent": Mock(),
            "left_view": Mock(),
            "right_view": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_lane_rect": Mock(return_value=None),
            "get_plate_rect": Mock(return_value=None),
            "get_active_rect": Mock(return_value=None),
            "stop_capture": Mock(),
            "start_timer": Mock(),
        }

    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_start_replay_cancelled(self, mock_dialog, mock_deps):
        """start_replay should return False when file dialog cancelled."""
        mock_dialog.return_value = ("", "")
        rc = ReplayController(**mock_deps)

        result = rc.start_replay()

        assert result is False
        assert rc.is_active is False

    @patch("ui.controllers.replay_controller.cv2.VideoCapture")
    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_start_replay_invalid_file(self, mock_dialog, mock_cv_capture, mock_deps):
        """start_replay should return False when video file cannot be opened."""
        mock_dialog.return_value = ("invalid.avi", "")
        mock_capture = Mock()
        mock_capture.isOpened.return_value = False
        mock_cv_capture.return_value = mock_capture

        rc = ReplayController(**mock_deps)
        result = rc.start_replay()

        assert result is False
        mock_deps["status_label"].setText.assert_called_with("Failed to open replay video.")

    @patch("ui.controllers.replay_controller.cv2.VideoCapture")
    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_start_replay_success(self, mock_dialog, mock_cv_capture, mock_deps):
        """start_replay should return True when video opens successfully."""
        mock_dialog.return_value = ("test.avi", "")
        mock_capture = Mock()
        mock_capture.isOpened.return_value = True
        mock_cv_capture.return_value = mock_capture

        rc = ReplayController(**mock_deps)
        result = rc.start_replay()

        assert result is True
        assert rc.is_active is True
        mock_deps["stop_capture"].assert_called_once()
        mock_deps["start_timer"].assert_called_once()
        mock_deps["status_label"].setText.assert_called_with("Replay mode.")


class TestStopReplay:
    """Tests for stopping video replay."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.camera.pixfmt = "GRAY8"
        config.detector.filters.min_area = 10
        config.detector.filters.max_area = 1000
        config.detector.filters.min_circularity = 0.5
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0
        config.detector.frame_diff_threshold = 30
        config.detector.bg_diff_threshold = 40
        config.detector.bg_alpha = 0.01
        config.detector.edge_threshold = 100
        config.detector.blob_threshold = 127
        config.detector.runtime_budget_ms = 10
        config.detector.crop_padding_px = 20
        config.detector.min_consecutive = 2
        config.detector.mode = "MODE_A"

        return {
            "parent": Mock(),
            "left_view": Mock(),
            "right_view": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_lane_rect": Mock(return_value=None),
            "get_plate_rect": Mock(return_value=None),
            "get_active_rect": Mock(return_value=None),
            "stop_capture": Mock(),
            "start_timer": Mock(),
        }

    @patch("ui.controllers.replay_controller.cv2.VideoCapture")
    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_stop_replay_releases_capture(self, mock_dialog, mock_cv_capture, mock_deps):
        """stop_replay should release video capture."""
        mock_dialog.return_value = ("test.avi", "")
        mock_capture = Mock()
        mock_capture.isOpened.return_value = True
        mock_cv_capture.return_value = mock_capture

        rc = ReplayController(**mock_deps)
        rc.start_replay()
        rc.stop_replay()

        mock_capture.release.assert_called_once()
        assert rc.is_active is False

    def test_stop_replay_no_active_replay(self, mock_deps):
        """stop_replay should handle no active replay gracefully."""
        rc = ReplayController(**mock_deps)
        rc.stop_replay()  # Should not raise
        assert rc.is_active is False


class TestTogglePause:
    """Tests for pause toggling."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.camera.pixfmt = "GRAY8"
        config.detector.filters.min_area = 10
        config.detector.filters.max_area = 1000
        config.detector.filters.min_circularity = 0.5
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0
        config.detector.frame_diff_threshold = 30
        config.detector.bg_diff_threshold = 40
        config.detector.bg_alpha = 0.01
        config.detector.edge_threshold = 100
        config.detector.blob_threshold = 127
        config.detector.runtime_budget_ms = 10
        config.detector.crop_padding_px = 20
        config.detector.min_consecutive = 2
        config.detector.mode = "MODE_A"

        return {
            "parent": Mock(),
            "left_view": Mock(),
            "right_view": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_lane_rect": Mock(return_value=None),
            "get_plate_rect": Mock(return_value=None),
            "get_active_rect": Mock(return_value=None),
            "stop_capture": Mock(),
            "start_timer": Mock(),
        }

    def test_toggle_pause_no_replay(self, mock_deps):
        """toggle_pause should do nothing when no replay active."""
        rc = ReplayController(**mock_deps)
        rc.toggle_pause()  # Should not raise
        assert rc.is_paused is False

    @patch("ui.controllers.replay_controller.cv2.VideoCapture")
    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_toggle_pause_during_replay(self, mock_dialog, mock_cv_capture, mock_deps):
        """toggle_pause should toggle pause state during replay."""
        mock_dialog.return_value = ("test.avi", "")
        mock_capture = Mock()
        mock_capture.isOpened.return_value = True
        mock_cv_capture.return_value = mock_capture

        rc = ReplayController(**mock_deps)
        rc.start_replay()

        assert rc.is_paused is False
        rc.toggle_pause()
        assert rc.is_paused is True
        mock_deps["status_label"].setText.assert_called_with("Replay paused.")

        rc.toggle_pause()
        assert rc.is_paused is False
        mock_deps["status_label"].setText.assert_called_with("Replay mode.")


class TestUpdateReplay:
    """Tests for replay frame updates."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.camera.pixfmt = "GRAY8"
        config.detector.filters.min_area = 10
        config.detector.filters.max_area = 1000
        config.detector.filters.min_circularity = 0.5
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0
        config.detector.frame_diff_threshold = 30
        config.detector.bg_diff_threshold = 40
        config.detector.bg_alpha = 0.01
        config.detector.edge_threshold = 100
        config.detector.blob_threshold = 127
        config.detector.runtime_budget_ms = 10
        config.detector.crop_padding_px = 20
        config.detector.min_consecutive = 2
        config.detector.mode = "MODE_A"

        return {
            "parent": Mock(),
            "left_view": Mock(),
            "right_view": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_lane_rect": Mock(return_value=None),
            "get_plate_rect": Mock(return_value=None),
            "get_active_rect": Mock(return_value=None),
            "stop_capture": Mock(),
            "start_timer": Mock(),
        }

    def test_update_replay_no_active(self, mock_deps):
        """update_replay should return False when no replay active."""
        rc = ReplayController(**mock_deps)
        result = rc.update_replay()
        assert result is False

    @patch("ui.controllers.replay_controller.cv2.VideoCapture")
    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_update_replay_paused(self, mock_dialog, mock_cv_capture, mock_deps):
        """update_replay should return False when paused."""
        mock_dialog.return_value = ("test.avi", "")
        mock_capture = Mock()
        mock_capture.isOpened.return_value = True
        mock_cv_capture.return_value = mock_capture

        rc = ReplayController(**mock_deps)
        rc.start_replay()
        rc.toggle_pause()

        result = rc.update_replay()
        assert result is False

    @patch("ui.controllers.replay_controller.frame_to_pixmap")
    @patch("ui.controllers.replay_controller.cv2.VideoCapture")
    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_update_replay_end_of_video(self, mock_dialog, mock_cv_capture, mock_pixmap, mock_deps):
        """update_replay should stop when video ends."""
        mock_dialog.return_value = ("test.avi", "")
        mock_capture = Mock()
        mock_capture.isOpened.return_value = True
        mock_capture.read.return_value = (False, None)  # No more frames
        mock_cv_capture.return_value = mock_capture

        rc = ReplayController(**mock_deps)
        rc.start_replay()
        result = rc.update_replay()

        assert result is False
        mock_deps["status_label"].setText.assert_called_with("Replay finished.")


class TestStepFrame:
    """Tests for single-frame stepping."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.camera.pixfmt = "GRAY8"
        config.detector.filters.min_area = 10
        config.detector.filters.max_area = 1000
        config.detector.filters.min_circularity = 0.5
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0
        config.detector.frame_diff_threshold = 30
        config.detector.bg_diff_threshold = 40
        config.detector.bg_alpha = 0.01
        config.detector.edge_threshold = 100
        config.detector.blob_threshold = 127
        config.detector.runtime_budget_ms = 10
        config.detector.crop_padding_px = 20
        config.detector.min_consecutive = 2
        config.detector.mode = "MODE_A"

        return {
            "parent": Mock(),
            "left_view": Mock(),
            "right_view": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_lane_rect": Mock(return_value=None),
            "get_plate_rect": Mock(return_value=None),
            "get_active_rect": Mock(return_value=None),
            "stop_capture": Mock(),
            "start_timer": Mock(),
        }

    def test_step_frame_no_replay(self, mock_deps):
        """step_frame should do nothing when no replay active."""
        rc = ReplayController(**mock_deps)
        rc.step_frame()  # Should not raise

    @patch("ui.controllers.replay_controller.cv2.VideoCapture")
    @patch("ui.controllers.replay_controller.QtWidgets.QFileDialog.getOpenFileName")
    def test_step_frame_advances_one_frame(self, mock_dialog, mock_cv_capture, mock_deps):
        """step_frame should advance by one frame and pause."""
        mock_dialog.return_value = ("test.avi", "")
        mock_capture = Mock()
        mock_capture.isOpened.return_value = True
        # Return no frame to trigger end-of-video which avoids cv2 processing
        mock_capture.read.return_value = (False, None)
        mock_cv_capture.return_value = mock_capture

        rc = ReplayController(**mock_deps)
        rc.start_replay()
        rc.step_frame()

        # Should be paused after stepping (even if video ended)
        assert rc.is_paused is True
        # Should have attempted to read one frame
        mock_capture.read.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
