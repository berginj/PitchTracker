"""Unit tests for RecordingController.

Tests the extracted RecordingController class from MainWindow refactoring.
Covers recording lifecycle and output directory management.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ui.controllers.recording_controller import RecordingController


class TestRecordingControllerInit:
    """Tests for RecordingController initialization."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies for RecordingController."""
        config = Mock()
        summary = Mock()
        summary.pitch_count = 5

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_session_name": Mock(return_value="test-session"),
            "set_session_name": Mock(),
            "get_output_dir": Mock(return_value=str(tmp_path / "output")),
            "set_output_dir_widget": Mock(),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_pitcher_name": Mock(return_value="TestPitcher"),
            "get_location_profile": Mock(return_value="TestLocation"),
            "health_check": Mock(return_value=True),
            "start_recording_service": Mock(),
            "stop_recording_service": Mock(),
            "set_record_directory": Mock(),
            "set_manual_speed_mph": Mock(),
            "get_session_summary": Mock(return_value=summary),
            "get_session_dir": Mock(return_value=tmp_path / "sessions" / "test"),
        }

    def test_initialization(self, mock_deps):
        """RecordingController should initialize with provided dependencies."""
        rc = RecordingController(**mock_deps)
        # Should not raise


class TestDefaultSessionName:
    """Tests for default session name generation."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_session_name": Mock(return_value=""),
            "set_session_name": Mock(),
            "get_output_dir": Mock(return_value=""),
            "set_output_dir_widget": Mock(),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_pitcher_name": Mock(return_value="JohnDoe"),
            "get_location_profile": Mock(return_value="TestLocation"),
            "health_check": Mock(return_value=True),
            "start_recording_service": Mock(),
            "stop_recording_service": Mock(),
            "set_record_directory": Mock(),
            "set_manual_speed_mph": Mock(),
            "get_session_summary": Mock(),
            "get_session_dir": Mock(),
        }

    def test_default_session_name_with_pitcher(self, mock_deps):
        """default_session_name should include pitcher name."""
        rc = RecordingController(**mock_deps)

        name = rc.default_session_name()

        assert name.startswith("JohnDoe-")
        assert len(name.split("-")) == 3  # pitcher-date-time

    def test_default_session_name_no_pitcher(self, mock_deps):
        """default_session_name should use 'pitcher' if no name set."""
        mock_deps["get_pitcher_name"] = Mock(return_value=None)
        rc = RecordingController(**mock_deps)

        name = rc.default_session_name()

        assert name.startswith("pitcher-")


class TestStartRecording:
    """Tests for starting recording."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        summary = Mock()
        summary.pitch_count = 0

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_session_name": Mock(return_value="test-session"),
            "set_session_name": Mock(),
            "get_output_dir": Mock(return_value=""),
            "set_output_dir_widget": Mock(),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_pitcher_name": Mock(return_value="Pitcher"),
            "get_location_profile": Mock(return_value="Location"),
            "health_check": Mock(return_value=True),
            "start_recording_service": Mock(),
            "stop_recording_service": Mock(),
            "set_record_directory": Mock(),
            "set_manual_speed_mph": Mock(),
            "get_session_summary": Mock(return_value=summary),
            "get_session_dir": Mock(),
        }

    def test_start_recording_success(self, mock_deps):
        """start_recording should start recording when health check passes."""
        rc = RecordingController(**mock_deps)

        result = rc.start_recording()

        assert result is True
        mock_deps["start_recording_service"].assert_called_once_with(
            "test-session", "review"
        )
        mock_deps["status_label"].setText.assert_called_with("Recording...")

    @patch("ui.controllers.recording_controller.QtWidgets.QMessageBox")
    def test_start_recording_health_check_fail(self, mock_msgbox, mock_deps):
        """start_recording should fail when health check fails."""
        mock_deps["health_check"] = Mock(return_value=False)
        rc = RecordingController(**mock_deps)

        result = rc.start_recording()

        assert result is False
        mock_msgbox.warning.assert_called_once()
        mock_deps["start_recording_service"].assert_not_called()

    def test_start_recording_empty_session_name(self, mock_deps):
        """start_recording should generate default name if empty."""
        mock_deps["get_session_name"] = Mock(return_value="")
        rc = RecordingController(**mock_deps)

        result = rc.start_recording()

        assert result is True
        # Should have called set_session_name with generated name
        mock_deps["set_session_name"].assert_called_once()
        call_args = mock_deps["set_session_name"].call_args[0][0]
        assert call_args.startswith("Pitcher-")


class TestStopRecording:
    """Tests for stopping recording."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        summary = Mock()
        summary.pitch_count = 10

        config_path = tmp_path / "config.yaml"
        config_path.write_text("recording: {}")

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(),
            "get_config_path": Mock(return_value=config_path),
            "get_session_name": Mock(return_value="test-session"),
            "set_session_name": Mock(),
            "get_output_dir": Mock(return_value=""),
            "set_output_dir_widget": Mock(),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_pitcher_name": Mock(return_value="Pitcher"),
            "get_location_profile": Mock(return_value="Location"),
            "health_check": Mock(return_value=True),
            "start_recording_service": Mock(),
            "stop_recording_service": Mock(),
            "set_record_directory": Mock(),
            "set_manual_speed_mph": Mock(),
            "get_session_summary": Mock(return_value=summary),
            "get_session_dir": Mock(return_value=tmp_path / "sessions"),
        }

    @patch("ui.controllers.recording_controller.SessionSummaryDialog")
    def test_stop_recording(self, mock_dialog, mock_deps):
        """stop_recording should stop service and show summary."""
        mock_dialog_instance = Mock()
        mock_dialog.return_value = mock_dialog_instance
        rc = RecordingController(**mock_deps)

        rc.stop_recording()

        mock_deps["stop_recording_service"].assert_called_once()
        mock_deps["status_label"].setText.assert_called_with("Recorded pitches: 10")
        mock_dialog.assert_called_once()
        mock_dialog_instance.exec.assert_called_once()


class TestTrainingCapture:
    """Tests for training capture mode."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_session_name": Mock(return_value="training-session"),
            "set_session_name": Mock(),
            "get_output_dir": Mock(return_value=""),
            "set_output_dir_widget": Mock(),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_pitcher_name": Mock(return_value="Pitcher"),
            "get_location_profile": Mock(return_value="Location"),
            "health_check": Mock(return_value=True),
            "start_recording_service": Mock(),
            "stop_recording_service": Mock(),
            "set_record_directory": Mock(),
            "set_manual_speed_mph": Mock(),
            "get_session_summary": Mock(),
            "get_session_dir": Mock(),
        }

    def test_start_training_capture_success(self, mock_deps):
        """start_training_capture should start recording in training mode."""
        rc = RecordingController(**mock_deps)

        result = rc.start_training_capture()

        assert result is True
        mock_deps["start_recording_service"].assert_called_once_with(
            "training-session", "training"
        )
        mock_deps["status_label"].setText.assert_called_with("Training capture...")

    @patch("ui.controllers.recording_controller.QtWidgets.QMessageBox")
    def test_start_training_capture_health_check_fail(self, mock_msgbox, mock_deps):
        """start_training_capture should fail when health check fails."""
        mock_deps["health_check"] = Mock(return_value=False)
        rc = RecordingController(**mock_deps)

        result = rc.start_training_capture()

        assert result is False
        mock_msgbox.warning.assert_called_once()


class TestOutputDirectory:
    """Tests for output directory management."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("recording: {}")

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(),
            "get_config_path": Mock(return_value=config_path),
            "get_session_name": Mock(return_value=""),
            "set_session_name": Mock(),
            "get_output_dir": Mock(return_value=""),
            "set_output_dir_widget": Mock(),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_pitcher_name": Mock(return_value="Pitcher"),
            "get_location_profile": Mock(return_value="Location"),
            "health_check": Mock(return_value=True),
            "start_recording_service": Mock(),
            "stop_recording_service": Mock(),
            "set_record_directory": Mock(),
            "set_manual_speed_mph": Mock(),
            "get_session_summary": Mock(),
            "get_session_dir": Mock(),
        }

    def test_set_output_dir(self, mock_deps, tmp_path):
        """set_output_dir should update widget, service, and config."""
        rc = RecordingController(**mock_deps)
        new_path = str(tmp_path / "new_output")

        rc.set_output_dir(new_path)

        mock_deps["set_output_dir_widget"].assert_called_once_with(new_path)
        mock_deps["set_record_directory"].assert_called_once_with(Path(new_path))

    def test_set_output_dir_empty(self, mock_deps):
        """set_output_dir should do nothing for empty path."""
        rc = RecordingController(**mock_deps)

        rc.set_output_dir("")

        mock_deps["set_output_dir_widget"].assert_not_called()
        mock_deps["set_record_directory"].assert_not_called()

    @patch("ui.controllers.recording_controller.QtWidgets.QFileDialog")
    def test_browse_output(self, mock_dialog, mock_deps, tmp_path):
        """browse_output should open dialog and set directory."""
        mock_dialog.getExistingDirectory.return_value = str(tmp_path / "selected")
        rc = RecordingController(**mock_deps)

        result = rc.browse_output()

        assert result == str(tmp_path / "selected")
        mock_dialog.getExistingDirectory.assert_called_once()
        mock_deps["set_output_dir_widget"].assert_called_once()

    @patch("ui.controllers.recording_controller.QtWidgets.QFileDialog")
    def test_browse_output_cancelled(self, mock_dialog, mock_deps):
        """browse_output should return None if cancelled."""
        mock_dialog.getExistingDirectory.return_value = ""
        rc = RecordingController(**mock_deps)

        result = rc.browse_output()

        assert result is None
        mock_deps["set_output_dir_widget"].assert_not_called()


class TestManualSpeed:
    """Tests for manual speed override."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies."""
        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            "get_session_name": Mock(return_value=""),
            "set_session_name": Mock(),
            "get_output_dir": Mock(return_value=""),
            "set_output_dir_widget": Mock(),
            "get_roi_path": Mock(return_value=tmp_path / "rois.json"),
            "get_pitcher_name": Mock(return_value="Pitcher"),
            "get_location_profile": Mock(return_value="Location"),
            "health_check": Mock(return_value=True),
            "start_recording_service": Mock(),
            "stop_recording_service": Mock(),
            "set_record_directory": Mock(),
            "set_manual_speed_mph": Mock(),
            "get_session_summary": Mock(),
            "get_session_dir": Mock(),
        }

    def test_set_manual_speed(self, mock_deps):
        """set_manual_speed should set speed in service."""
        rc = RecordingController(**mock_deps)

        rc.set_manual_speed(85.5)

        mock_deps["set_manual_speed_mph"].assert_called_once_with(85.5)

    def test_set_manual_speed_zero(self, mock_deps):
        """set_manual_speed should set None for zero value."""
        rc = RecordingController(**mock_deps)

        rc.set_manual_speed(0.0)

        mock_deps["set_manual_speed_mph"].assert_called_once_with(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
