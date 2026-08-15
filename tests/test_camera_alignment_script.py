"""Characterization tests for camera alignment script collaborators."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from exceptions import CalibrationInputError
from scripts.camera_alignment_support import (
    analyze_horizontal_alignment,
    analyze_rotation,
    analyze_vertical_alignment,
    load_frame,
    print_alignment_report,
)


def test_load_frame_validates_local_image_paths(tmp_path: Path) -> None:
    image_path = tmp_path / "pair.png"
    cv2.imwrite(str(image_path), np.zeros((8, 8, 3), dtype=np.uint8))

    assert load_frame(image_path).shape == (8, 8, 3)
    with pytest.raises(CalibrationInputError):
        load_frame(tmp_path / "missing.png")

    text_path = tmp_path / "pair.txt"
    text_path.write_text("not an image")
    with pytest.raises(CalibrationInputError, match="Could not load image"):
        load_frame(text_path)

    webp_path = tmp_path / "pair.webp"
    assert cv2.imwrite(str(webp_path), np.zeros((8, 8, 3), dtype=np.uint8))
    assert load_frame(webp_path).shape == (8, 8, 3)


def test_alignment_metrics_preserve_threshold_semantics() -> None:
    left = np.array([[0, 0], [10, 0], [20, 0], [30, 0]], dtype=np.float32)
    right = np.array([[4, 1], [16, 1], [26, 1], [34, 1]], dtype=np.float32)
    translated = left + np.array([5, 1], dtype=np.float32)

    vertical = analyze_vertical_alignment(left, right)
    horizontal = analyze_horizontal_alignment(left, right)
    rotation = analyze_rotation(left, translated)

    assert vertical["status"] == "EXCELLENT"
    assert vertical["mean_vertical_disparity_px"] == pytest.approx(1.0)
    assert horizontal["mean_horizontal_disparity_px"] == pytest.approx(-5.0)
    assert horizontal["severity"] == "ok"
    assert rotation["rotation_deg"] == pytest.approx(0.0, abs=0.01)


def test_alignment_report_preserves_sections_and_exit_decision(capsys) -> None:
    vertical = {
        "status": "POOR",
        "severity": "error",
        "message": "height mismatch",
        "mean_vertical_disparity_px": 12.0,
        "max_vertical_disparity_px": 20.0,
        "recommendation": "Adjust camera heights to match",
    }
    horizontal = {
        "status": "GOOD",
        "severity": "ok",
        "message": "parallel",
        "std_horizontal_disparity_px": 4.0,
        "position_disparity_correlation": 0.05,
        "recommendation": None,
    }
    rotation = {
        "status": "GOOD",
        "severity": "ok",
        "message": "level",
        "rotation_deg": 0.2,
        "recommendation": None,
    }

    assert print_alignment_report(vertical, horizontal, rotation, 75) is False
    report = capsys.readouterr().out
    assert "CAMERA ALIGNMENT REPORT" in report
    assert "VERTICAL ALIGNMENT (Height)" in report
    assert "HORIZONTAL ALIGNMENT (Convergence)" in report
    assert "ROTATION ALIGNMENT (Roll)" in report
    assert "Fix the issues above before attempting calibration." in report
