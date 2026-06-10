"""Unit tests for CaptureController.

Tests the extracted CaptureController class from MainWindow refactoring.
Covers camera capture lifecycle and pre-capture validation.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ui.controllers.capture_controller import CaptureController


class TestCaptureControllerInit:
    """Tests for CaptureController initialization."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies for CaptureController."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.detector.type = "classical"
        config.detector.model_path = ""
        config.recording.output_dir = str(tmp_path / "output")

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_left_serial": Mock(return_value="left_serial"),
            "get_right_serial": Mock(return_value="right_serial"),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_lane_path": Mock(return_value=tmp_path / "lane_rois.json"),
            "start_timer": Mock(),
            "stop_timer": Mock(),
            "stop_replay": Mock(),
            "start_capture_service": Mock(),
            "stop_capture_service": Mock(),
        }

    def test_initialization(self, mock_deps):
        """CaptureController should initialize with provided dependencies."""
        cc = CaptureController(**mock_deps)
        # Should not raise


class TestStartCapture:
    """Tests for starting capture."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.detector.type = "classical"
        config.detector.model_path = ""
        config.recording.output_dir = str(tmp_path / "output")

        # Create the output dir
        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        # Create config file
        (tmp_path / "config.yaml").write_text("camera: {}")
        # Create ROI files
        (tmp_path / "rois.json").write_text("{}")
        (tmp_path / "lane_rois.json").write_text("{}")

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_left_serial": Mock(return_value="left_serial"),
            "get_right_serial": Mock(return_value="right_serial"),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_lane_path": Mock(return_value=tmp_path / "lane_rois.json"),
            "start_timer": Mock(),
            "stop_timer": Mock(),
            "stop_replay": Mock(),
            "start_capture_service": Mock(),
            "stop_capture_service": Mock(),
        }

    def test_start_capture_no_left_serial(self, mock_deps):
        """start_capture should fail without left serial."""
        mock_deps["get_left_serial"] = Mock(return_value=None)
        cc = CaptureController(**mock_deps)

        result = cc.start_capture()

        assert result is False
        mock_deps["status_label"].setText.assert_called_with("Enter both serials.")

    def test_start_capture_no_right_serial(self, mock_deps):
        """start_capture should fail without right serial."""
        mock_deps["get_right_serial"] = Mock(return_value=None)
        cc = CaptureController(**mock_deps)

        result = cc.start_capture()

        assert result is False
        mock_deps["status_label"].setText.assert_called_with("Enter both serials.")

    @patch("ui.controllers.capture_controller.validate_config_file")
    def test_start_capture_success(self, mock_validate, mock_deps):
        """start_capture should start capture when valid."""
        cc = CaptureController(**mock_deps)

        result = cc.start_capture()

        assert result is True
        mock_deps["stop_replay"].assert_called_once()
        mock_deps["start_capture_service"].assert_called_once()
        mock_deps["start_timer"].assert_called_once()
        mock_deps["status_label"].setText.assert_called_with("Capturing.")


class TestStopCapture:
    """Tests for stopping capture."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_left_serial": Mock(return_value="left"),
            "get_right_serial": Mock(return_value="right"),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_lane_path": Mock(return_value=tmp_path / "lane_rois.json"),
            "start_timer": Mock(),
            "stop_timer": Mock(),
            "stop_replay": Mock(),
            "start_capture_service": Mock(),
            "stop_capture_service": Mock(),
        }

    def test_stop_capture(self, mock_deps):
        """stop_capture should stop timer and service."""
        cc = CaptureController(**mock_deps)

        cc.stop_capture()

        mock_deps["stop_timer"].assert_called_once()
        mock_deps["stop_capture_service"].assert_called_once()
        mock_deps["status_label"].setText.assert_called_with("Stopped.")


class TestRestartCapture:
    """Tests for restarting capture."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        config = Mock()
        config.ui.refresh_hz = 30
        config.detector.type = "classical"
        config.detector.model_path = ""
        config.recording.output_dir = str(tmp_path / "output")

        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        (tmp_path / "config.yaml").write_text("camera: {}")
        (tmp_path / "rois.json").write_text("{}")
        (tmp_path / "lane_rois.json").write_text("{}")

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_left_serial": Mock(return_value="left"),
            "get_right_serial": Mock(return_value="right"),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_lane_path": Mock(return_value=tmp_path / "lane_rois.json"),
            "start_timer": Mock(),
            "stop_timer": Mock(),
            "stop_replay": Mock(),
            "start_capture_service": Mock(),
            "stop_capture_service": Mock(),
        }

    @patch("ui.controllers.capture_controller.validate_config_file")
    def test_restart_capture(self, mock_validate, mock_deps):
        """restart_capture should stop and start capture."""
        cc = CaptureController(**mock_deps)

        cc.restart_capture()

        mock_deps["stop_timer"].assert_called_once()
        mock_deps["stop_capture_service"].assert_called_once()
        mock_deps["start_capture_service"].assert_called_once()


class TestPreCaptureCheck:
    """Tests for pre-capture validation."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        config = Mock()
        config.detector.type = "classical"
        config.detector.model_path = ""
        config.recording.output_dir = str(tmp_path / "output")

        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        (tmp_path / "config.yaml").write_text("camera: {}")
        (tmp_path / "rois.json").write_text("{}")
        (tmp_path / "lane_rois.json").write_text("{}")

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_left_serial": Mock(return_value="left"),
            "get_right_serial": Mock(return_value="right"),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_lane_path": Mock(return_value=tmp_path / "lane_rois.json"),
            "start_timer": Mock(),
            "stop_timer": Mock(),
            "stop_replay": Mock(),
            "start_capture_service": Mock(),
            "stop_capture_service": Mock(),
        }

    @patch("ui.controllers.capture_controller.validate_config_file")
    def test_pre_capture_check_pass(self, mock_validate, mock_deps):
        """pre_capture_check should pass when all checks pass."""
        cc = CaptureController(**mock_deps)

        result = cc.pre_capture_check()

        assert result is True

    @patch("ui.controllers.capture_controller.QtWidgets.QMessageBox")
    @patch("ui.controllers.capture_controller.validate_config_file")
    def test_pre_capture_check_ml_no_model(self, mock_validate, mock_msgbox, mock_deps):
        """pre_capture_check should fail for ML mode without model path."""
        mock_deps["get_config"].return_value.detector.type = "ml"
        mock_deps["get_config"].return_value.detector.model_path = ""
        cc = CaptureController(**mock_deps)

        result = cc.pre_capture_check()

        assert result is False
        mock_msgbox.critical.assert_called_once()

    @patch("ui.controllers.capture_controller.QtWidgets.QMessageBox")
    @patch("ui.controllers.capture_controller.validate_config_file")
    def test_pre_capture_check_warning_no_roi(self, mock_validate, mock_msgbox, mock_deps, tmp_path):
        """pre_capture_check should show warning for missing ROI file."""
        # Remove ROI file
        (tmp_path / "rois.json").unlink()
        mock_msgbox.warning.return_value = mock_msgbox.Yes
        cc = CaptureController(**mock_deps)

        result = cc.pre_capture_check()

        # Should show warning but allow continue if user clicks Yes
        mock_msgbox.warning.assert_called_once()
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
