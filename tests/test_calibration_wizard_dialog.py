"""Characterization tests for the calibration wizard facade."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtWidgets  # noqa: E402

from configs.settings import load_config  # noqa: E402
from ui.dialogs.calibration_wizard_dialog import CalibrationWizardDialog  # noqa: E402
from ui.dialogs.calibration_wizard_support import CalibrationWizardSupport  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


class _WizardParent(QtWidgets.QMainWindow):
    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self._path = config_path
        self._config = load_config(config_path)
        self._left_input = QtWidgets.QComboBox()
        self._right_input = QtWidgets.QComboBox()
        self._left_input.addItem("Left", "left-serial")
        self._right_input.addItem("Right", "right-serial")
        self._calibration_overlay = SimpleNamespace(
            target_found=False,
            fiducial_error="",
            fiducial_detections=[],
            fiducial_ids={"plate": 1, "rubber": 2},
        )
        self._roi_manager = SimpleNamespace(
            lane_rect=None,
            lane_rect_right=None,
            plate_rect=None,
        )
        self._status_label = QtWidgets.QLabel()
        self._service = Mock()
        self._service.get_latest_detections.return_value = {}
        self._service.is_capturing.return_value = False
        self._stop_capture = Mock()
        self._start_capture = Mock()
        self._open_calibration_guide = Mock()
        self._open_quick_calibrate = Mock()
        self._open_plate_calibrate = Mock()
        self._cue_card_test = Mock()
        self._refresh_devices = Mock()
        self._propose_right_lane = Mock()
        self._set_roi_mode = Mock()
        self._set_target_overlay = Mock()
        self._set_fiducial_overlay = Mock()

    def _config_path(self) -> Path:
        return self._path

    def _health_ok(self) -> bool:
        return True


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "default.yaml"
    shutil.copyfile(Path("configs/default.yaml"), path)
    return path


def test_wizard_preserves_step_order_and_navigation(qapp, config_path: Path) -> None:
    parent = _WizardParent(config_path)
    dialog = CalibrationWizardDialog(parent)

    assert [step["title"] for step in dialog._steps] == [
        "Start Capture + Health Check",
        "Calibration Target (Checkerboard)",
        "Fiducials (Plate + Rubber)",
        "Lane ROI",
        "Plate ROI",
        "Quick Calibrate (Checkerboard)",
        "Plate Plane Calibration",
        "Detector Test",
        "Ready",
    ]
    assert dialog._title.text().startswith("Step 1 of 9")
    assert dialog._action_button.text() == "Start Capture"
    assert dialog._status_timer.isActive()
    parent._set_target_overlay.assert_called_with(False)
    parent._set_fiducial_overlay.assert_called_with(False)

    dialog._skip_step()

    assert dialog._index == 1
    assert dialog._skipped_steps == ["Start Capture + Health Check"]
    assert dialog._action_button.text() == "Open Guide"
    parent._set_target_overlay.assert_called_with(True)
    dialog.close()


def test_support_persists_baseline_and_completion_log(config_path: Path) -> None:
    parent = _WizardParent(config_path)
    support = CalibrationWizardSupport(parent)

    support.update_baseline(2.25)
    support.write_log(["Detector Test"])

    assert load_config(config_path).stereo.baseline_ft == pytest.approx(2.25)
    assert "27.0 inches" in parent._status_label.text()
    payload = json.loads((config_path.parent / "calibration_wizard_log.json").read_text())
    assert payload["runs"][-1]["skipped_steps"] == ["Detector Test"]


def test_support_characterizes_fiducial_and_detector_validation(config_path: Path) -> None:
    parent = _WizardParent(config_path)
    support = CalibrationWizardSupport(parent)
    parent._calibration_overlay.fiducial_detections = [
        SimpleNamespace(tag_id=1),
        SimpleNamespace(tag_id=2),
    ]
    parent._service.get_latest_detections.return_value = {"left": [object()]}

    assert support.validate_fiducials() is True
    assert support.validate_detector_activity() is True

    parent._calibration_overlay.fiducial_error = "detector unavailable"
    parent._service.get_latest_detections.side_effect = RuntimeError("offline")
    assert support.validate_fiducials() is False
    assert support.validate_detector_activity() is False
