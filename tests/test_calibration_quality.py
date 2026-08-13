"""Characterization tests for calib.calibration_quality module."""

from __future__ import annotations

import numpy as np
import pytest

from calib.calibration_quality import (
    _compute_per_image_errors,
    _rate_calibration_quality,
    _rate_quick_calibration_quality,
    _validate_stereo_geometry,
)
from exceptions import CalibrationExecutionError


class TestValidateStereoGeometry:
    def test_accepts_reasonable_geometry(self):
        _validate_stereo_geometry(0.4, 0.5, np.eye(3))

    def test_rejects_tiny_baseline(self):
        with pytest.raises(CalibrationExecutionError):
            _validate_stereo_geometry(0.4, 0.001, np.eye(3))

    def test_rejects_nonfinite_rms(self):
        with pytest.raises(CalibrationExecutionError):
            _validate_stereo_geometry(float("nan"), 0.5, np.eye(3))

    def test_rejects_absurd_rms(self):
        with pytest.raises(CalibrationExecutionError):
            _validate_stereo_geometry(999.0, 0.5, np.eye(3))

    def test_rejects_nonfinite_fundamental(self):
        with pytest.raises(CalibrationExecutionError):
            _validate_stereo_geometry(0.4, 0.5, np.full((3, 3), np.inf))

    def test_rejects_none_fundamental(self):
        with pytest.raises(CalibrationExecutionError):
            _validate_stereo_geometry(0.4, 0.5, None)


class TestRateCalibrationQuality:
    def test_excellent(self):
        q = _rate_calibration_quality(0.3, 20)
        assert q["rating"] == "EXCELLENT"

    def test_good(self):
        q = _rate_calibration_quality(0.7, 15)
        assert q["rating"] == "GOOD"

    def test_acceptable(self):
        q = _rate_calibration_quality(1.5, 12)
        assert q["rating"] == "ACCEPTABLE"

    def test_poor(self):
        q = _rate_calibration_quality(3.0, 5)
        assert q["rating"] == "POOR"


class TestRateQuickCalibrationQuality:
    def test_good(self):
        q = _rate_quick_calibration_quality(1.5, 5)
        assert q["rating"] == "GOOD"
        assert "90-95%" in q["description"]

    def test_acceptable(self):
        q = _rate_quick_calibration_quality(2.5, 4)
        assert q["rating"] == "ACCEPTABLE"

    def test_poor(self):
        q = _rate_quick_calibration_quality(4.0, 3)
        assert q["rating"] == "POOR"


class TestComputePerImageErrors:
    def test_returns_errors_list(self):
        obj = [np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0],
                         [1, 1, 0]], dtype=np.float32)]
        img = [np.array([[100, 100], [200, 100], [100, 200],
                         [200, 200]], dtype=np.float32)]
        mtx = np.array([[500, 0, 320], [0, 500, 240],
                        [0, 0, 1]], dtype=np.float64)
        dist = np.zeros(5, dtype=np.float64)
        R = np.eye(3, dtype=np.float64)
        T = np.array([[-100.0], [0.0], [0.0]], dtype=np.float64)

        errors = _compute_per_image_errors(
            obj, img, img, mtx, dist, mtx, dist, R, T
        )
        assert len(errors) == 1
        assert "left_rms" in errors[0]
        assert "right_rms" in errors[0]
        assert "combined_rms" in errors[0]
