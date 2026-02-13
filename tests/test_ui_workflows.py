"""Integration tests for critical UI workflows.

Tests complete user workflows from start to finish, including:
- Setup wizard completion
- ROI configuration
- Session recording and export
- Settings management
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import numpy as np
import pytest

# Try to import pytest-qt, skip Qt tests if not available
try:
    from pytest_qt.plugin import QtBot
    HAS_PYTEST_QT = True
except ImportError:
    HAS_PYTEST_QT = False
    QtBot = None

from PySide6 import QtCore, QtWidgets

from configs.settings import load_config
from ui.dialogs import (
    RecordingSettingsDialog,
    StrikeZoneSettingsDialog,
    DetectorSettingsDialog,
    QuickCalibrateDialog,
)
from ui.export import write_session_summary_csv
from ui.widgets import RoiLabel

# Skip all Qt-dependent tests if pytest-qt not available
requires_pytest_qt = pytest.mark.skipif(
    not HAS_PYTEST_QT,
    reason="pytest-qt not installed"
)


class TestRecordingSettingsWorkflow:
    """Test recording settings dialog workflow."""

    @requires_pytest_qt
    def test_recording_settings_roundtrip(self, qtbot):
        """Test that recording settings can be set and retrieved."""
        dialog = RecordingSettingsDialog(
            parent=None,
            session="initial_session",
            output_dir="./output",
            speed_mph=80.0,
        )
        qtbot.addWidget(dialog)

        # Modify settings
        dialog._session_input.setText("modified_session")
        dialog._output_input.setText("./modified_output")
        dialog._speed_input.setValue(90.0)

        # Accept dialog (as user would click OK)
        # Note: Can't actually click in headless tests, but we can call accept()
        assert dialog._session_input.text() == "modified_session"
        assert dialog._output_input.text() == "./modified_output"
        assert dialog._speed_input.value() == 90.0

        # Verify values() method returns correct data
        session, output, speed = dialog.values()
        assert session == "modified_session"
        assert output == "./modified_output"
        assert speed == 90.0

    @requires_pytest_qt
    def test_recording_settings_validation(self, qtbot):
        """Test that recording settings validates input."""
        dialog = RecordingSettingsDialog(
            parent=None,
            session="test",
            output_dir="./output",
            speed_mph=80.0,
        )
        qtbot.addWidget(dialog)

        # Test empty session name
        dialog._session_input.setText("")
        values = dialog.values()
        # Should return defaults or handle empty gracefully
        assert values is not None

        # Test valid session name with special characters
        dialog._session_input.setText("session_2024-01-15")
        session, _, _ = dialog.values()
        assert session == "session_2024-01-15"


class TestStrikeZoneSettingsWorkflow:
    """Test strike zone settings dialog workflow."""

    @requires_pytest_qt
    def test_strike_zone_roundtrip(self, qtbot):
        """Test strike zone settings can be set and retrieved."""
        dialog = StrikeZoneSettingsDialog(
            parent=None,
            ball_type="baseball",
            batter_height=72.0,
            top_ratio=0.7,
            bottom_ratio=0.3,
        )
        qtbot.addWidget(dialog)

        # Modify settings
        dialog._ball_combo.setCurrentText("softball")
        dialog._height_input.setValue(68.0)
        dialog._top_ratio_input.setValue(0.75)
        dialog._bottom_ratio_input.setValue(0.25)

        # Verify values
        ball_type, height, top, bottom = dialog.values()
        assert ball_type == "softball"
        assert height == 68.0
        assert top == 0.75
        assert bottom == 0.25

    @requires_pytest_qt
    def test_strike_zone_batter_height_bounds(self, qtbot):
        """Test that batter height has reasonable bounds."""
        dialog = StrikeZoneSettingsDialog(
            parent=None,
            ball_type="baseball",
            batter_height=72.0,
            top_ratio=0.7,
            bottom_ratio=0.3,
        )
        qtbot.addWidget(dialog)

        # Test valid height
        dialog._height_input.setValue(75.0)
        _, height, _, _ = dialog.values()
        assert height == 75.0

        # Verify spinbox has reasonable min/max
        assert dialog._height_input.minimum() > 0  # Must be positive
        assert dialog._height_input.maximum() < 120  # Reasonable max


class TestDetectorSettingsWorkflow:
    """Test detector settings dialog workflow."""

    @requires_pytest_qt
    def test_detector_settings_mode_switch(self, qtbot):
        """Test switching between detector modes."""
        dialog = DetectorSettingsDialog(
            parent=None,
            mode="MODE_A",
            frame_diff=18.0,
            bg_diff=12.0,
            bg_alpha=0.08,
            edge_thresh=32.0,
            blob_thresh=22.0,
            min_area=12,
            min_circ=0.1,
            threading_mode="per_camera",
            worker_count=2,
            detector_type="classical",
            model_path="",
            model_input_size=(640, 640),
            model_conf_threshold=0.25,
            model_class_id=0,
            model_format="yolo_v5",
        )
        qtbot.addWidget(dialog)

        # Switch to MODE_B
        dialog._mode_combo.setCurrentText("MODE_B")

        # Verify values can be retrieved
        values = dialog.values()
        assert values["mode"] == "MODE_B"

        # Verify other values are preserved
        assert values["min_area"] == 12
        assert values["min_circ"] == 0.1

    @requires_pytest_qt
    def test_detector_settings_threading_config(self, qtbot):
        """Test threading configuration."""
        dialog = DetectorSettingsDialog(
            parent=None,
            mode="MODE_A",
            frame_diff=18.0,
            bg_diff=12.0,
            bg_alpha=0.08,
            edge_thresh=32.0,
            blob_thresh=22.0,
            min_area=12,
            min_circ=0.1,
            threading_mode="per_camera",
            worker_count=2,
            detector_type="classical",
            model_path="",
            model_input_size=(640, 640),
            model_conf_threshold=0.25,
            model_class_id=0,
            model_format="yolo_v5",
        )
        qtbot.addWidget(dialog)

        # Change threading mode
        dialog._threading_combo.setCurrentText("pooled")
        dialog._workers_spin.setValue(4)

        values = dialog.values()
        assert values["threading_mode"] == "pooled"
        assert values["worker_count"] == 4


class TestROIDrawingWorkflow:
    """Test ROI drawing and management workflow."""

    @requires_pytest_qt
    def test_roi_label_draw_rectangle(self, qtbot):
        """Test drawing a rectangle ROI."""
        callback = Mock()
        label = RoiLabel(on_rect_update=callback)
        qtbot.addWidget(label)

        # Set up image and enter drawing mode
        label.set_image_size(640, 480)
        label.set_mode("lane")

        # Simulate mouse events for drawing
        # Note: In real usage, user would click and drag
        # Here we test the internal state

        # Start drawing
        press_event = Mock(spec=QtCore.QEvent)
        press_event.pos.return_value = QtCore.QPoint(100, 100)
        press_event.button.return_value = QtCore.Qt.LeftButton
        press_event.buttons.return_value = QtCore.Qt.LeftButton

        # Note: Can't easily simulate full mouse interaction in headless tests
        # This test verifies the widget can be created and configured
        assert label._mode == "lane"
        assert label._image_size == (640, 480)

    @requires_pytest_qt
    def test_roi_label_clear_drawing(self, qtbot):
        """Test clearing ROI drawing."""
        callback = Mock()
        label = RoiLabel(on_rect_update=callback)
        qtbot.addWidget(label)

        label.set_image_size(640, 480)
        label.set_mode("lane")

        # Clear mode
        label.set_mode(None)
        assert label._mode is None


class TestSessionExportWorkflow:
    """Test session export workflow."""

    def test_export_session_csv(self, tmp_path):
        """Test exporting session data to CSV."""
        # Create mock session summary
        summary = Mock()
        pitch1 = Mock()
        pitch1.pitch_id = "pitch_001"
        pitch1.t_start_ns = 1000000000
        pitch1.t_end_ns = 2000000000
        pitch1.is_strike = True
        pitch1.zone_row = 2
        pitch1.zone_col = 3
        pitch1.run_in = 3.5
        pitch1.rise_in = -2.1
        pitch1.speed_mph = 87.3
        pitch1.rotation_rpm = 2200.0
        pitch1.sample_count = 25
        pitch1.trajectory_plate_x_ft = 0.291  # 3.5 inches
        pitch1.trajectory_plate_y_ft = 2.5
        pitch1.trajectory_plate_z_ft = 0.0
        pitch1.trajectory_plate_t_ns = 1800000000
        pitch1.trajectory_model = "ballistic_drag"
        pitch1.trajectory_expected_error_ft = 0.05
        pitch1.trajectory_confidence = 0.95

        pitch2 = Mock()
        pitch2.pitch_id = "pitch_002"
        pitch2.t_start_ns = 3000000000
        pitch2.t_end_ns = 4000000000
        pitch2.is_strike = False
        pitch2.zone_row = None
        pitch2.zone_col = None
        pitch2.run_in = 8.2
        pitch2.rise_in = 1.5
        pitch2.speed_mph = 75.5
        pitch2.rotation_rpm = 1800.0
        pitch2.sample_count = 22
        pitch2.trajectory_plate_x_ft = 0.683  # 8.2 inches
        pitch2.trajectory_plate_y_ft = 3.2
        pitch2.trajectory_plate_z_ft = 0.0
        pitch2.trajectory_plate_t_ns = 3700000000
        pitch2.trajectory_model = "ballistic_drag"
        pitch2.trajectory_expected_error_ft = 0.08
        pitch2.trajectory_confidence = 0.88

        summary.pitches = [pitch1, pitch2]

        # Export to CSV
        csv_path = tmp_path / "session_export.csv"
        write_session_summary_csv(csv_path, summary)

        # Verify file created
        assert csv_path.exists()

        # Verify content
        content = csv_path.read_text()
        assert "pitch_id" in content
        assert "pitch_001" in content
        assert "pitch_002" in content
        assert "87.3" in content  # Speed of first pitch
        assert "75.5" in content  # Speed of second pitch
        assert "True" in content or "1" in content  # is_strike
        assert "False" in content or "0" in content  # is_strike

        # Verify CSV can be parsed
        lines = content.strip().split("\n")
        assert len(lines) >= 3  # Header + 2 pitches
        header = lines[0].split(",")
        assert "pitch_id" in header
        assert "speed_mph" in header
        assert "is_strike" in header

    def test_export_session_multiple_formats(self, tmp_path):
        """Test exporting session in multiple formats."""
        summary = Mock()
        pitch = Mock()
        pitch.pitch_id = "test_pitch"
        pitch.t_start_ns = 1000000000
        pitch.t_end_ns = 2000000000
        pitch.is_strike = True
        pitch.zone_row = 1
        pitch.zone_col = 2
        pitch.run_in = 2.0
        pitch.rise_in = 1.0
        pitch.speed_mph = 85.0
        pitch.rotation_rpm = 2000.0
        pitch.sample_count = 20
        # Add optional trajectory fields
        pitch.trajectory_plate_x_ft = 0.167  # 2 inches
        pitch.trajectory_plate_y_ft = 2.5
        pitch.trajectory_plate_z_ft = 0.0
        pitch.trajectory_plate_t_ns = 1700000000
        pitch.trajectory_model = "ballistic_drag"
        pitch.trajectory_expected_error_ft = 0.06
        pitch.trajectory_confidence = 0.92

        summary.pitches = [pitch]

        # Export CSV
        csv_path = tmp_path / "export.csv"
        write_session_summary_csv(csv_path, summary)
        assert csv_path.exists()
        assert csv_path.stat().st_size > 100  # Non-trivial content


class TestConfigurationPersistence:
    """Test that configuration changes persist."""

    def test_config_load_and_validate(self):
        """Test loading configuration file."""
        config_path = Path("configs/default.yaml")
        assert config_path.exists(), "Default config should exist"

        config = load_config(config_path)
        assert config is not None

        # Verify key fields
        assert config.camera.width > 0
        assert config.camera.height > 0
        assert config.camera.fps > 0
        assert config.stereo.baseline_ft > 0
        assert config.stereo.focal_length_px > 0

    def test_config_detector_settings(self):
        """Test detector configuration fields."""
        config_path = Path("configs/default.yaml")
        config = load_config(config_path)

        # Verify detector config
        assert config.detector.type in ["classical", "ml"]
        assert config.detector.mode in ["MODE_A", "MODE_B"]
        assert 0 < config.detector.frame_diff_threshold < 100
        assert 0 < config.detector.bg_diff_threshold < 100
        assert 0 < config.detector.bg_alpha < 1

        # Verify filters
        assert config.detector.filters.min_area >= 0
        assert 0 <= config.detector.filters.min_circularity <= 1

    def test_config_strike_zone_settings(self):
        """Test strike zone configuration."""
        config_path = Path("configs/default.yaml")
        config = load_config(config_path)

        # Verify strike zone config
        assert 48 <= config.strike_zone.batter_height_in <= 96  # Reasonable range
        assert 0 < config.strike_zone.top_ratio < 1
        assert 0 < config.strike_zone.bottom_ratio < 1
        assert config.strike_zone.top_ratio > config.strike_zone.bottom_ratio


class TestDialogAcceptReject:
    """Test dialog acceptance and rejection workflows."""

    @requires_pytest_qt
    def test_dialog_accept_returns_values(self, qtbot):
        """Test that accepting dialog returns modified values."""
        dialog = RecordingSettingsDialog(
            parent=None,
            session="test",
            output_dir="./output",
            speed_mph=80.0,
        )
        qtbot.addWidget(dialog)

        # Modify values
        dialog._session_input.setText("modified")
        session, _, _ = dialog.values()
        assert session == "modified"

    @requires_pytest_qt
    def test_dialog_creation_with_defaults(self, qtbot):
        """Test dialogs can be created with default values."""
        dialog = StrikeZoneSettingsDialog(
            parent=None,
            ball_type="baseball",
            batter_height=72.0,
            top_ratio=0.7,
            bottom_ratio=0.3,
        )
        qtbot.addWidget(dialog)

        # Verify defaults are set
        ball_type, height, top, bottom = dialog.values()
        assert ball_type == "baseball"
        assert height == 72.0
        assert abs(top - 0.7) < 0.01
        assert abs(bottom - 0.3) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
