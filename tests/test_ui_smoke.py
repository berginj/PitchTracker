"""Functional smoke tests for UI components after refactoring.

These tests verify that UI components can be instantiated and
function correctly with the new module structure.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock

import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from ui.geometry import normalize_rect, points_to_rect, polygon_to_rect, rect_to_polygon, roi_overlays


class TestGeometryFunctions:
    """Test geometry utility functions."""

    def test_points_to_rect(self):
        """Test converting QPoint pair to rectangle."""
        start = QtCore.QPoint(10, 20)
        end = QtCore.QPoint(100, 80)
        rect = points_to_rect(start, end)

        assert rect is not None
        assert rect == (10, 20, 100, 80)  # x1, y1, x2, y2

    def test_normalize_rect_within_bounds(self):
        """Test normalizing rectangle within image bounds."""
        rect = (10, 20, 100, 80)  # x1, y1, x2, y2
        image_size = (640, 480)

        normalized = normalize_rect(rect, image_size)
        assert normalized == rect  # Should be unchanged

    def test_normalize_rect_out_of_bounds(self):
        """Test normalizing rectangle that extends beyond bounds."""
        rect = (600, 400, 700, 500)  # Extends beyond 640x480
        image_size = (640, 480)

        normalized = normalize_rect(rect, image_size)
        assert normalized is not None
        x1, y1, x2, y2 = normalized
        assert x2 <= 639
        assert y2 <= 479

    def test_rect_to_polygon(self):
        """Test converting rectangle to polygon points."""
        rect = (10, 20, 100, 80)  # x1, y1, x2, y2
        polygon = rect_to_polygon(rect)

        assert polygon is not None
        assert len(polygon) == 4
        assert polygon[0] == (10, 20)  # Top-left
        assert polygon[1] == (100, 20)  # Top-right
        assert polygon[2] == (100, 80)  # Bottom-right
        assert polygon[3] == (10, 80)  # Bottom-left

    def test_polygon_to_rect(self):
        """Test converting polygon to bounding rectangle."""
        polygon = [(10, 20), (100, 20), (100, 80), (10, 80)]
        rect = polygon_to_rect(polygon)

        assert rect is not None
        assert rect == (10, 20, 100, 80)  # x1, y1, x2, y2

    def test_roi_overlays_empty(self):
        """Test generating overlays with no ROIs."""
        overlays = roi_overlays(None, None, None)
        assert overlays == []

    def test_roi_overlays_single(self):
        """Test generating overlays with single ROI."""
        lane_rect = (10, 20, 100, 80)
        overlays = roi_overlays(lane_rect, None, None)

        assert len(overlays) == 1
        rect, color = overlays[0]
        assert rect == lane_rect
        assert isinstance(color, QtGui.QColor)


class TestDrawingFunctions:
    """Test drawing utility functions."""

    def test_frame_to_pixmap_grayscale(self):
        """Test converting grayscale frame to pixmap."""
        from ui.drawing import frame_to_pixmap

        frame = np.zeros((480, 640), dtype=np.uint8)
        pixmap = frame_to_pixmap(frame)

        assert pixmap is not None
        assert isinstance(pixmap, QtGui.QPixmap)
        assert not pixmap.isNull()

    def test_frame_to_pixmap_color(self):
        """Test converting color frame to pixmap."""
        from ui.drawing import frame_to_pixmap

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pixmap = frame_to_pixmap(frame)

        assert pixmap is not None
        assert isinstance(pixmap, QtGui.QPixmap)
        assert not pixmap.isNull()

    def test_frame_to_pixmap_with_overlays(self):
        """Test converting frame with ROI overlays."""
        from ui.drawing import frame_to_pixmap

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        overlays = [((10, 20, 100, 80), QtGui.QColor(255, 0, 0))]

        pixmap = frame_to_pixmap(frame, overlays=overlays)

        assert pixmap is not None
        assert not pixmap.isNull()


class TestDeviceUtils:
    """Test device utility functions."""

    def test_current_serial_with_data(self, qtbot):
        """Test extracting serial from QComboBox with itemData."""
        from ui.device_utils import current_serial

        combo = QtWidgets.QComboBox()
        combo.addItem("Camera 1", "SN12345")
        combo.setCurrentIndex(0)

        serial = current_serial(combo)
        assert serial == "SN12345"

    def test_current_serial_with_text(self, qtbot):
        """Test extracting serial from QComboBox text."""
        from ui.device_utils import current_serial

        combo = QtWidgets.QComboBox()
        combo.addItem("SN12345")
        combo.setCurrentIndex(0)

        serial = current_serial(combo)
        assert serial == "SN12345"

    def test_current_serial_empty(self, qtbot):
        """Test extracting serial from empty QComboBox."""
        from ui.device_utils import current_serial

        combo = QtWidgets.QComboBox()
        serial = current_serial(combo)
        assert serial == ""


class TestExportFunctions:
    """Test export utility functions."""

    def test_write_session_summary_csv(self, tmp_path):
        """Test writing session summary to CSV."""
        from ui.export import write_session_summary_csv

        # Create mock summary with pitches
        summary = Mock()
        pitch1 = Mock()
        pitch1.pitch_id = "pitch_001"
        pitch1.t_start_ns = 1000000
        pitch1.t_end_ns = 2000000
        pitch1.is_strike = True
        pitch1.zone_row = 1
        pitch1.zone_col = 2
        pitch1.run_in = 2.5
        pitch1.rise_in = 1.3
        pitch1.speed_mph = 85.5
        pitch1.rotation_rpm = 2100.0
        pitch1.sample_count = 30

        summary.pitches = [pitch1]

        csv_path = tmp_path / "test_summary.csv"
        write_session_summary_csv(csv_path, summary)

        assert csv_path.exists()
        content = csv_path.read_text()
        assert "pitch_id" in content
        assert "pitch_001" in content
        assert "85.5" in content


class TestRoiLabel:
    """Test RoiLabel widget."""

    def test_roi_label_creation(self, qtbot):
        """Test creating RoiLabel widget."""
        from ui.widgets import RoiLabel

        callback = Mock()
        label = RoiLabel(on_rect_update=callback)
        qtbot.addWidget(label)

        assert label is not None
        assert isinstance(label, QtWidgets.QLabel)

    def test_roi_label_set_mode(self, qtbot):
        """Test setting ROI drawing mode."""
        from ui.widgets import RoiLabel

        callback = Mock()
        label = RoiLabel(on_rect_update=callback)
        qtbot.addWidget(label)

        label.set_mode("lane")
        label.set_mode(None)
        # If we get here without errors, mode setting works

    def test_roi_label_set_image_size(self, qtbot):
        """Test setting image size."""
        from ui.widgets import RoiLabel

        callback = Mock()
        label = RoiLabel(on_rect_update=callback)
        qtbot.addWidget(label)

        label.set_image_size(640, 480)
        size = label.image_size()
        assert size == (640, 480)


class TestDialogs:
    """Test dialog classes can be instantiated."""

    def test_calibration_guide_creation(self, qtbot):
        """Test creating CalibrationGuide dialog."""
        from ui.dialogs import CalibrationGuide

        dialog = CalibrationGuide()
        qtbot.addWidget(dialog)

        assert dialog is not None
        assert dialog.windowTitle() == "Calibration Guide"

    def test_checklist_dialog_creation(self, qtbot):
        """Test creating ChecklistDialog."""
        from ui.dialogs import ChecklistDialog

        dialog = ChecklistDialog()
        qtbot.addWidget(dialog)

        assert dialog is not None
        assert dialog.windowTitle() == "Pre-Recording Checklist"

    def test_startup_dialog_creation(self, qtbot):
        """Test creating StartupDialog."""
        from ui.dialogs import StartupDialog

        dialog = StartupDialog()
        qtbot.addWidget(dialog)

        assert dialog is not None
        assert dialog.windowTitle() == "Startup"

    def test_recording_settings_dialog_creation(self, qtbot):
        """Test creating RecordingSettingsDialog."""
        from ui.dialogs import RecordingSettingsDialog

        dialog = RecordingSettingsDialog(
            parent=None,
            session="test_session",
            output_dir="./output",
            speed_mph=80.0,
        )
        qtbot.addWidget(dialog)

        assert dialog is not None
        assert dialog.windowTitle() == "Recording Settings"

    def test_strike_zone_settings_dialog_creation(self, qtbot):
        """Test creating StrikeZoneSettingsDialog."""
        from ui.dialogs import StrikeZoneSettingsDialog

        dialog = StrikeZoneSettingsDialog(
            parent=None,
            ball_type="baseball",
            batter_height=72.0,
            top_ratio=0.7,
            bottom_ratio=0.3,
        )
        qtbot.addWidget(dialog)

        assert dialog is not None
        assert dialog.windowTitle() == "Strike Zone Settings"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
