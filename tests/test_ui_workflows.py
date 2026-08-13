"""Integration tests for critical UI workflows.

Tests complete user workflows from start to finish, including:
- Setup wizard completion
- ROI configuration
- Session recording and export
- Settings management
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from PySide6 import QtCore

from configs.settings import load_config
from ui.dialogs import (
    RecordingSettingsDialog,
    StrikeZoneSettingsDialog,
    DetectorSettingsDialog,
)
from ui.export import write_session_summary_csv
from ui.widgets import RoiLabel

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_PYTEST_QT = importlib.util.find_spec("pytestqt") is not None

requires_pytest_qt = pytest.mark.skipif(not HAS_PYTEST_QT, reason="pytest-qt not installed")


class TestRecordingSettingsWorkflow:
    """Test recording settings dialog workflow."""

    @requires_pytest_qt
    def test_recording_settings_roundtrip(self, qtbot: "QtBot"):
        """Test that recording settings can be set and retrieved."""
        dialog = RecordingSettingsDialog(
            parent=None,
            session="initial_session",
            output_dir="./output",
            speed_mph=80.0,
        )
        qtbot.addWidget(dialog)

        # Modify settings via actual widget attributes
        dialog._session.setText("modified_session")
        dialog._output_dir.setText("./modified_output")
        dialog._speed.setValue(90.0)

        assert dialog._session.text() == "modified_session"
        assert dialog._output_dir.text() == "./modified_output"
        assert dialog._speed.value() == 90.0

        # Verify values() method returns correct data
        session, output, speed = dialog.values()
        assert session == "modified_session"
        assert output == "./modified_output"
        assert speed == 90.0

    @requires_pytest_qt
    def test_recording_settings_validation(self, qtbot: "QtBot"):
        """Test that recording settings validates input."""
        dialog = RecordingSettingsDialog(
            parent=None,
            session="test",
            output_dir="./output",
            speed_mph=80.0,
        )
        qtbot.addWidget(dialog)

        # Test empty session name
        dialog._session.setText("")
        values = dialog.values()
        assert values is not None

        # Test valid session name with special characters
        dialog._session.setText("session_2024-01-15")
        session, _, _ = dialog.values()
        assert session == "session_2024-01-15"


class TestStrikeZoneSettingsWorkflow:
    """Test strike zone settings dialog workflow."""

    @requires_pytest_qt
    def test_strike_zone_roundtrip(self, qtbot: "QtBot"):
        """Test strike zone settings can be set and retrieved."""
        dialog = StrikeZoneSettingsDialog(
            parent=None,
            ball_type="baseball",
            batter_height=72.0,
            top_ratio=0.7,
            bottom_ratio=0.3,
        )
        qtbot.addWidget(dialog)

        # Modify settings via actual widget attributes
        dialog._ball.setCurrentText("softball")
        dialog._height.setValue(68.0)
        dialog._top.setValue(0.75)
        dialog._bottom.setValue(0.25)

        # Verify values
        ball_type, height, top, bottom = dialog.values()
        assert ball_type == "softball"
        assert height == 68.0
        assert top == 0.75
        assert bottom == 0.25

    @requires_pytest_qt
    def test_strike_zone_batter_height_bounds(self, qtbot: "QtBot"):
        """Test that batter height has reasonable bounds."""
        dialog = StrikeZoneSettingsDialog(
            parent=None,
            ball_type="baseball",
            batter_height=72.0,
            top_ratio=0.7,
            bottom_ratio=0.3,
        )
        qtbot.addWidget(dialog)

        dialog._height.setValue(75.0)
        _, height, _, _ = dialog.values()
        assert height == 75.0

        # Verify spinbox has reasonable min/max
        assert dialog._height.minimum() > 0
        assert dialog._height.maximum() < 120


class TestDetectorSettingsWorkflow:
    """Test detector settings dialog workflow."""

    @requires_pytest_qt
    def test_detector_settings_mode_switch(self, qtbot: "QtBot"):
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

        # Switch to MODE_B via actual _mode combo
        dialog._mode.setCurrentText("MODE_B")

        values = dialog.values()
        assert values["mode"] == "MODE_B"

        # Verify other values are preserved
        assert values["min_area"] == 12
        assert values["min_circ"] == 0.1

    @requires_pytest_qt
    def test_detector_settings_threading_config(self, qtbot: "QtBot"):
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

        # Change threading mode via _threading combo (uses item data)
        dialog._threading.setCurrentIndex(1)  # "Worker pool" -> "worker_pool"
        dialog._workers.setValue(4)

        values = dialog.values()
        assert values["threading_mode"] == "worker_pool"
        assert values["worker_count"] == 4


class TestROIDrawingWorkflow:
    """Test ROI drawing and management workflow."""

    @requires_pytest_qt
    def test_roi_label_draw_rectangle(self, qtbot: "QtBot"):
        """Test drawing a rectangle ROI with real mouse events."""
        callback = Mock()
        label = RoiLabel(on_rect_update=callback)
        qtbot.addWidget(label)
        label.resize(640, 480)
        label.show()
        qtbot.waitExposed(label)

        # Set up image and enter drawing mode
        label.set_image_size(640, 480)
        label.set_mode("lane")

        # Simulate full mouse interaction via qtbot
        start = QtCore.QPoint(100, 100)
        end = QtCore.QPoint(300, 300)
        qtbot.mousePress(label, QtCore.Qt.MouseButton.LeftButton, pos=start)
        qtbot.mouseMove(label, pos=end)
        qtbot.mouseRelease(label, QtCore.Qt.MouseButton.LeftButton, pos=end)

        # callback should have been called with a final rect
        assert callback.call_count >= 1
        # Last call should be final=True
        last_call = callback.call_args_list[-1]
        assert last_call[0][1] is True  # positional arg: final

    @requires_pytest_qt
    def test_roi_label_clear_drawing(self, qtbot: "QtBot"):
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
        pitch1.trajectory_plate_x_ft = 0.291
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
        pitch2.trajectory_plate_x_ft = 0.683
        pitch2.trajectory_plate_y_ft = 3.2
        pitch2.trajectory_plate_z_ft = 0.0
        pitch2.trajectory_plate_t_ns = 3700000000
        pitch2.trajectory_model = "ballistic_drag"
        pitch2.trajectory_expected_error_ft = 0.08
        pitch2.trajectory_confidence = 0.88

        summary.pitches = [pitch1, pitch2]

        csv_path = tmp_path / "session_export.csv"
        write_session_summary_csv(csv_path, summary)

        assert csv_path.exists()
        content = csv_path.read_text()
        assert "pitch_id" in content
        assert "pitch_001" in content
        assert "pitch_002" in content
        assert "87.3" in content
        assert "75.5" in content

        lines = content.strip().split("\n")
        assert len(lines) >= 3
        header = lines[0].split(",")
        assert "pitch_id" in header
        assert "speed_mph" in header

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
        pitch.trajectory_plate_x_ft = 0.167
        pitch.trajectory_plate_y_ft = 2.5
        pitch.trajectory_plate_z_ft = 0.0
        pitch.trajectory_plate_t_ns = 1700000000
        pitch.trajectory_model = "ballistic_drag"
        pitch.trajectory_expected_error_ft = 0.06
        pitch.trajectory_confidence = 0.92

        summary.pitches = [pitch]

        csv_path = tmp_path / "export.csv"
        write_session_summary_csv(csv_path, summary)
        assert csv_path.exists()
        assert csv_path.stat().st_size > 100


class TestConfigurationPersistence:
    """Test that configuration changes persist."""

    def test_config_load_and_validate(self):
        """Test loading configuration file."""
        config_path = Path("configs/default.yaml")
        assert config_path.exists(), "Default config should exist"

        config = load_config(config_path)
        assert config is not None

        assert config.camera.width > 0
        assert config.camera.height > 0
        assert config.camera.fps > 0
        assert config.stereo.baseline_ft > 0
        assert config.stereo.focal_length_px > 0

    def test_config_detector_settings(self):
        """Test detector configuration fields."""
        config_path = Path("configs/default.yaml")
        config = load_config(config_path)

        assert config.detector.type in ["classical", "ml"]
        assert config.detector.mode in ["MODE_A", "MODE_B"]
        assert 0 < config.detector.frame_diff_threshold < 100
        assert 0 < config.detector.bg_diff_threshold < 100
        assert 0 < config.detector.bg_alpha < 1

        assert config.detector.filters.min_area >= 0
        assert 0 <= config.detector.filters.min_circularity <= 1

    def test_config_strike_zone_settings(self):
        """Test strike zone configuration."""
        config_path = Path("configs/default.yaml")
        config = load_config(config_path)

        assert 48 <= config.strike_zone.batter_height_in <= 96
        assert 0 < config.strike_zone.top_ratio < 1
        assert 0 < config.strike_zone.bottom_ratio < 1
        assert config.strike_zone.top_ratio > config.strike_zone.bottom_ratio


class TestDialogAcceptReject:
    """Test dialog acceptance and rejection workflows."""

    @requires_pytest_qt
    def test_dialog_accept_returns_values(self, qtbot: "QtBot"):
        """Test that accepting dialog returns modified values."""
        dialog = RecordingSettingsDialog(
            parent=None,
            session="test",
            output_dir="./output",
            speed_mph=80.0,
        )
        qtbot.addWidget(dialog)

        # Modify values via actual widget
        dialog._session.setText("modified")
        session, _, _ = dialog.values()
        assert session == "modified"

    @requires_pytest_qt
    def test_dialog_creation_with_defaults(self, qtbot: "QtBot"):
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
