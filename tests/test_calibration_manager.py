"""Unit tests for CalibrationManager controller.

Tests the extracted CalibrationManager class from MainWindow refactoring.
Covers calibration workflows and dialog management.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from ui.controllers.calibration_manager import CalibrationManager


class TestCalibrationManagerInit:
    """Tests for CalibrationManager initialization."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies for CalibrationManager."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("stereo:\n  baseline_ft: 1.0\n  focal_length_px: 1200.0\n")
        return {
            "parent": Mock(),
            "config_path": config_path,
            "status_label": Mock(),
            "calib_summary": Mock(),
            "get_config": Mock(),
            "set_config": Mock(),
        }

    def test_initialization(self, mock_deps):
        """CalibrationManager should initialize with provided dependencies."""
        cm = CalibrationManager(**mock_deps)
        assert cm._parent is mock_deps["parent"]
        assert cm._config_path == mock_deps["config_path"]
        assert cm.wizard_is_open is False

    def test_wizard_initially_closed(self, mock_deps):
        """Calibration wizard should be closed initially."""
        cm = CalibrationManager(**mock_deps)
        assert cm.wizard_is_open is False


class TestCalibrationGuide:
    """Tests for calibration guide dialog."""

    @pytest.fixture
    def calibration_manager(self, tmp_path):
        """Create CalibrationManager with mocked dependencies."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("stereo:\n  baseline_ft: 1.0\n")
        return CalibrationManager(
            parent=Mock(),
            config_path=config_path,
            status_label=Mock(),
            calib_summary=Mock(),
            get_config=Mock(),
            set_config=Mock(),
        )

    @patch("ui.controllers.calibration_manager.CalibrationGuide")
    def test_open_calibration_guide(self, mock_dialog_class, calibration_manager):
        """open_calibration_guide should create and show dialog."""
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog

        calibration_manager.open_calibration_guide()

        mock_dialog_class.assert_called_once()
        mock_dialog.exec.assert_called_once()


class TestCalibrationWizard:
    """Tests for calibration wizard dialog."""

    @pytest.fixture
    def calibration_manager(self, tmp_path):
        """Create CalibrationManager with mocked dependencies."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("stereo:\n  baseline_ft: 1.0\n")
        return CalibrationManager(
            parent=Mock(),
            config_path=config_path,
            status_label=Mock(),
            calib_summary=Mock(),
            get_config=Mock(),
            set_config=Mock(),
        )

    @patch("ui.controllers.calibration_manager.CalibrationWizardDialog")
    def test_run_calibration_wizard_opens_dialog(self, mock_dialog_class, calibration_manager):
        """run_calibration_wizard should create and show wizard dialog."""
        mock_wizard = Mock()
        mock_dialog_class.return_value = mock_wizard

        calibration_manager.run_calibration_wizard()

        mock_dialog_class.assert_called_once()
        mock_wizard.setModal.assert_called_once_with(False)
        mock_wizard.show.assert_called_once()
        assert calibration_manager.wizard_is_open is True

    @patch("ui.controllers.calibration_manager.CalibrationWizardDialog")
    def test_run_calibration_wizard_raises_existing(self, mock_dialog_class, calibration_manager):
        """run_calibration_wizard should raise existing wizard if open."""
        # First call - opens wizard
        mock_wizard = Mock()
        mock_dialog_class.return_value = mock_wizard
        calibration_manager.run_calibration_wizard()

        # Reset mock call count
        mock_dialog_class.reset_mock()
        mock_wizard.reset_mock()

        # Second call - should raise existing
        calibration_manager.run_calibration_wizard()

        # Should not create new dialog
        mock_dialog_class.assert_not_called()
        # Should raise existing
        mock_wizard.raise_.assert_called_once()
        mock_wizard.activateWindow.assert_called_once()

    @patch("ui.controllers.calibration_manager.CalibrationWizardDialog")
    def test_wizard_closed_callback(self, mock_dialog_class, calibration_manager):
        """Wizard should clear reference when closed."""
        mock_wizard = Mock()
        mock_dialog_class.return_value = mock_wizard

        calibration_manager.run_calibration_wizard()
        assert calibration_manager.wizard_is_open is True

        # Simulate wizard closing
        calibration_manager._on_wizard_closed()
        assert calibration_manager.wizard_is_open is False


class TestQuickCalibrate:
    """Tests for quick calibration dialog."""

    @pytest.fixture
    def calibration_manager(self, tmp_path):
        """Create CalibrationManager with mocked dependencies."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("stereo:\n  baseline_ft: 1.0\n  focal_length_px: 1200.0\n")
        mock_config = Mock()
        mock_config.stereo.baseline_ft = 1.0
        mock_config.stereo.focal_length_px = 1200.0
        return CalibrationManager(
            parent=Mock(),
            config_path=config_path,
            status_label=Mock(),
            calib_summary=Mock(),
            get_config=Mock(return_value=mock_config),
            set_config=Mock(),
        )

    @patch("ui.controllers.calibration_manager.load_config")
    @patch("ui.controllers.calibration_manager.QuickCalibrateDialog")
    def test_quick_calibrate_cancelled(self, mock_dialog_class, mock_load, calibration_manager):
        """open_quick_calibrate should handle cancellation."""
        mock_dialog = Mock()
        mock_dialog.updated = False
        mock_dialog_class.return_value = mock_dialog

        calibration_manager.open_quick_calibrate()

        mock_dialog.exec.assert_called_once()
        mock_load.assert_not_called()  # Config not reloaded
        calibration_manager._set_config.assert_not_called()

    @patch("ui.controllers.calibration_manager.load_config")
    @patch("ui.controllers.calibration_manager.QuickCalibrateDialog")
    def test_quick_calibrate_success_with_values(self, mock_dialog_class, mock_load, calibration_manager):
        """open_quick_calibrate should update config on success."""
        mock_dialog = Mock()
        mock_dialog.updated = True
        mock_dialog.updates = {"baseline_ft": 1.5, "focal_length_px": 1250.0}
        mock_dialog_class.return_value = mock_dialog

        mock_config = Mock()
        mock_config.stereo.baseline_ft = 1.5
        mock_config.stereo.focal_length_px = 1250.0
        mock_load.return_value = mock_config

        calibration_manager.open_quick_calibrate()

        mock_load.assert_called_once()
        calibration_manager._set_config.assert_called_once_with(mock_config)
        # Check status message contains updated values
        status_text = calibration_manager._status_label.setText.call_args[0][0]
        assert "1.500" in status_text
        assert "1250.0" in status_text

    @patch("ui.controllers.calibration_manager.load_config")
    @patch("ui.controllers.calibration_manager.QuickCalibrateDialog")
    def test_quick_calibrate_success_no_values(self, mock_dialog_class, mock_load, calibration_manager):
        """open_quick_calibrate should handle success without specific values."""
        mock_dialog = Mock()
        mock_dialog.updated = True
        mock_dialog.updates = {}  # No specific updates
        mock_dialog_class.return_value = mock_dialog

        mock_config = Mock()
        mock_config.stereo.baseline_ft = 1.0
        mock_config.stereo.focal_length_px = 1200.0
        mock_load.return_value = mock_config

        calibration_manager.open_quick_calibrate()

        status_text = calibration_manager._status_label.setText.call_args[0][0]
        assert "Restart capture" in status_text


class TestPlateCalibrate:
    """Tests for plate plane calibration dialog."""

    @pytest.fixture
    def calibration_manager(self, tmp_path):
        """Create CalibrationManager with mocked dependencies."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("stereo:\n  baseline_ft: 1.0\n")
        return CalibrationManager(
            parent=Mock(),
            config_path=config_path,
            status_label=Mock(),
            calib_summary=Mock(),
            get_config=Mock(),
            set_config=Mock(),
        )

    @patch("ui.controllers.calibration_manager.PlatePlaneDialog")
    def test_plate_calibrate_cancelled(self, mock_dialog_class, calibration_manager):
        """open_plate_calibrate should handle cancellation."""
        from PySide6 import QtWidgets

        mock_dialog = Mock()
        mock_dialog.exec.return_value = QtWidgets.QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        calibration_manager.open_plate_calibrate()

        mock_dialog.values.assert_not_called()

    @patch("ui.controllers.calibration_manager.load_config")
    @patch("ui.controllers.calibration_manager.estimate_and_write")
    @patch("ui.controllers.calibration_manager.PlatePlaneDialog")
    def test_plate_calibrate_success(self, mock_dialog_class, mock_estimate, mock_load, calibration_manager):
        """open_plate_calibrate should update config on success."""
        from PySide6 import QtWidgets

        mock_dialog = Mock()
        mock_dialog.exec.return_value = QtWidgets.QDialog.Accepted
        mock_dialog.values.return_value = ("/path/left.png", "/path/right.png")
        mock_dialog_class.return_value = mock_dialog

        mock_estimate.return_value = 55.5  # Plate Z position
        mock_config = Mock()
        mock_load.return_value = mock_config

        calibration_manager.open_plate_calibrate()

        mock_estimate.assert_called_once()
        mock_load.assert_called_once()
        calibration_manager._set_config.assert_called_once_with(mock_config)
        status_text = calibration_manager._status_label.setText.call_args[0][0]
        assert "55.500" in status_text

    @patch("ui.controllers.calibration_manager.QtWidgets.QMessageBox")
    @patch("ui.controllers.calibration_manager.estimate_and_write")
    @patch("ui.controllers.calibration_manager.PlatePlaneDialog")
    def test_plate_calibrate_error(self, mock_dialog_class, mock_estimate, mock_msgbox, calibration_manager):
        """open_plate_calibrate should show error on failure."""
        from PySide6 import QtWidgets

        mock_dialog = Mock()
        mock_dialog.exec.return_value = QtWidgets.QDialog.Accepted
        mock_dialog.values.return_value = ("/path/left.png", "/path/right.png")
        mock_dialog_class.return_value = mock_dialog

        mock_estimate.side_effect = Exception("Calibration failed")

        calibration_manager.open_plate_calibrate()

        mock_msgbox.critical.assert_called_once()


class TestUpdateCalibSummary:
    """Tests for calibration summary updates."""

    @pytest.fixture
    def calibration_manager(self, tmp_path):
        """Create CalibrationManager with mocked dependencies."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("stereo:\n  baseline_ft: 1.0\n")
        mock_config = Mock()
        mock_config.stereo.baseline_ft = 1.234
        mock_config.stereo.focal_length_px = 1200.5
        return CalibrationManager(
            parent=Mock(),
            config_path=config_path,
            status_label=Mock(),
            calib_summary=Mock(),
            get_config=Mock(return_value=mock_config),
            set_config=Mock(),
        )

    def test_update_calib_summary(self, calibration_manager):
        """update_calib_summary should update summary label."""
        calibration_manager.update_calib_summary()

        summary_text = calibration_manager._calib_summary.setText.call_args[0][0]
        assert "1.234" in summary_text
        assert "1200.5" in summary_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
