"""Smoke tests for UI module imports after refactoring.

These tests verify that all UI modules can be imported successfully
and that the refactored structure maintains correct dependencies.
"""

from __future__ import annotations

import pytest


def test_main_window_import():
    """Test that MainWindow can be imported from ui module."""
    from ui import MainWindow

    assert MainWindow is not None


def test_main_window_direct_import():
    """Test that MainWindow can be imported directly."""
    from ui.main_window import MainWindow

    assert MainWindow is not None


def test_geometry_imports():
    """Test that geometry utilities can be imported."""
    from ui.geometry import (
        Overlay,
        Rect,
        normalize_rect,
        points_to_rect,
        polygon_to_rect,
        rect_to_polygon,
        roi_overlays,
    )

    assert normalize_rect is not None
    assert points_to_rect is not None
    assert polygon_to_rect is not None
    assert rect_to_polygon is not None
    assert roi_overlays is not None


def test_drawing_imports():
    """Test that drawing utilities can be imported."""
    from ui.drawing import frame_to_pixmap

    assert frame_to_pixmap is not None


def test_device_utils_imports():
    """Test that device utilities can be imported."""
    from ui.device_utils import (
        current_serial,
        probe_opencv_indices,
        probe_uvc_devices,
    )

    assert current_serial is not None
    assert probe_opencv_indices is not None
    assert probe_uvc_devices is not None


def test_export_imports():
    """Test that export functions can be imported."""
    from ui.export import (
        export_manifests_zip,
        export_session_summary_csv,
        export_session_summary_json,
        export_training_report,
        save_session_export,
        upload_session,
        write_session_summary_csv,
    )

    assert upload_session is not None
    assert save_session_export is not None
    assert export_session_summary_json is not None
    assert export_session_summary_csv is not None
    assert write_session_summary_csv is not None
    assert export_training_report is not None
    assert export_manifests_zip is not None


def test_widgets_imports():
    """Test that widget classes can be imported."""
    from ui.widgets import RoiLabel

    assert RoiLabel is not None


def test_roi_label_direct_import():
    """Test that RoiLabel can be imported directly."""
    from ui.widgets.roi_label import RoiLabel

    assert RoiLabel is not None


def test_all_dialogs_package_import():
    """Test that all dialogs can be imported from dialogs package."""
    from ui.dialogs import (
        CalibrationGuide,
        CalibrationWizardDialog,
        ChecklistDialog,
        DetectorSettingsDialog,
        PlatePlaneDialog,
        QuickCalibrateDialog,
        RecordingSettingsDialog,
        SessionSummaryDialog,
        StartupDialog,
        StrikeZoneSettingsDialog,
    )

    # Verify all dialog classes exist
    assert CalibrationGuide is not None
    assert CalibrationWizardDialog is not None
    assert ChecklistDialog is not None
    assert DetectorSettingsDialog is not None
    assert PlatePlaneDialog is not None
    assert QuickCalibrateDialog is not None
    assert RecordingSettingsDialog is not None
    assert SessionSummaryDialog is not None
    assert StartupDialog is not None
    assert StrikeZoneSettingsDialog is not None


def test_simple_dialogs_direct_import():
    """Test that simple dialogs can be imported directly."""
    from ui.dialogs.calibration_guide import CalibrationGuide
    from ui.dialogs.checklist_dialog import ChecklistDialog
    from ui.dialogs.detector_settings_dialog import DetectorSettingsDialog
    from ui.dialogs.recording_settings_dialog import RecordingSettingsDialog
    from ui.dialogs.session_summary_dialog import SessionSummaryDialog
    from ui.dialogs.startup_dialog import StartupDialog
    from ui.dialogs.strike_zone_settings_dialog import StrikeZoneSettingsDialog

    assert CalibrationGuide is not None
    assert ChecklistDialog is not None
    assert DetectorSettingsDialog is not None
    assert RecordingSettingsDialog is not None
    assert SessionSummaryDialog is not None
    assert StartupDialog is not None
    assert StrikeZoneSettingsDialog is not None


def test_calibration_dialogs_direct_import():
    """Test that calibration dialogs can be imported directly."""
    from ui.dialogs.calibration_wizard_dialog import CalibrationWizardDialog
    from ui.dialogs.plate_plane_dialog import PlatePlaneDialog
    from ui.dialogs.quick_calibrate_dialog import QuickCalibrateDialog

    assert CalibrationWizardDialog is not None
    assert PlatePlaneDialog is not None
    assert QuickCalibrateDialog is not None


def test_qt_app_entry_point():
    """Test that qt_app entry point module can be imported."""
    from ui import qt_app

    assert hasattr(qt_app, "parse_args")
    assert hasattr(qt_app, "main")
    assert callable(qt_app.parse_args)
    assert callable(qt_app.main)


def test_no_circular_imports():
    """Test that importing all modules doesn't cause circular import errors."""
    # This will fail if there are circular imports
    from ui import MainWindow
    from ui.dialogs import (
        CalibrationGuide,
        CalibrationWizardDialog,
        ChecklistDialog,
        DetectorSettingsDialog,
        PlatePlaneDialog,
        QuickCalibrateDialog,
        RecordingSettingsDialog,
        SessionSummaryDialog,
        StartupDialog,
        StrikeZoneSettingsDialog,
    )
    from ui.device_utils import current_serial, probe_opencv_indices, probe_uvc_devices
    from ui.drawing import frame_to_pixmap
    from ui.export import (
        export_manifests_zip,
        export_session_summary_csv,
        export_session_summary_json,
        export_training_report,
        save_session_export,
        upload_session,
        write_session_summary_csv,
    )
    from ui.geometry import (
        normalize_rect,
        points_to_rect,
        polygon_to_rect,
        rect_to_polygon,
        roi_overlays,
    )
    from ui.widgets import RoiLabel

    # If we got here without errors, no circular imports exist
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
