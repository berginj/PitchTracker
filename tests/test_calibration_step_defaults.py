from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
from PySide6 import QtCore

from ui.setup.steps.calibration_step import CalibrationStep


def _checkerboard_image(cols: int = 6, rows: int = 6, square_px: int = 70) -> np.ndarray:
    image = np.zeros((rows * square_px, cols * square_px), dtype=np.uint8)
    for row in range(rows):
        for col in range(cols):
            if (row + col) % 2 == 0:
                image[row * square_px : (row + 1) * square_px, col * square_px : (col + 1) * square_px] = 255
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


def test_calibration_step_defaults_to_manual_6x6_board(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    step = CalibrationStep(backend="opencv")
    qtbot.addWidget(step)

    assert step._pattern_cols == 6
    assert step._pattern_rows == 6
    assert step._square_mm == 30.0
    assert step._pattern_locked is True
    assert step._auto_detect_pattern_checkbox.isChecked() is False
    assert step._pattern_cols_spin.value() == 6
    assert step._pattern_rows_spin.value() == 6
    assert step._square_spin.value() == 30.0
    assert "Manual board: 6x6, 30.0 mm" in step._pattern_info_label.text()

    step._cached_dict_name = "DICT_6X6_250"
    step._update_pattern_info()

    assert "Manual board: 6x6, 30.0 mm" in step._pattern_info_label.text()


def test_manual_board_edits_stay_locked_until_auto_detect_is_enabled(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    step = CalibrationStep(backend="opencv")
    qtbot.addWidget(step)

    step._pattern_cols_spin.setValue(7)
    step._pattern_rows_spin.setValue(8)
    step._square_spin.setValue(40.0)

    assert step._pattern_cols == 7
    assert step._pattern_rows == 8
    assert step._square_mm == 40.0
    assert step._pattern_locked is True

    step._auto_detect_pattern_checkbox.setCheckState(QtCore.Qt.CheckState.Checked)
    assert step._pattern_locked is False

    step._auto_detect_pattern_checkbox.setCheckState(QtCore.Qt.CheckState.Unchecked)
    assert step._pattern_locked is True


def test_capture_validation_accepts_checkerboard_fallback_when_charuco_ids_fail(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    step = CalibrationStep(backend="opencv")
    qtbot.addWidget(step)
    image = _checkerboard_image()

    monkeypatch.setattr(step, "_detect_charuco_ids", lambda _image: (None, 200.0))

    valid, message = step._validate_capture_pair(image, image)

    assert valid is True
    assert "checkerboard fallback accepted" in message


def test_alignment_drift_check_does_not_block_fixed_camera_calibration(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    step = CalibrationStep(backend="opencv")
    qtbot.addWidget(step)
    step._baseline_alignment = SimpleNamespace()
    step._alignment_history.append(SimpleNamespace())

    abort_capture = step._check_alignment_drift(np.zeros((20, 20), dtype=np.uint8), np.zeros((20, 20), dtype=np.uint8))

    assert abort_capture is False
