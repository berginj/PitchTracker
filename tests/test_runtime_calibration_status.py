"""Tests for runtime calibration status helper."""

from __future__ import annotations

import numpy as np
import yaml

from calib.runtime_status import describe_runtime_calibration


def test_describe_runtime_calibration_full_matrix(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    np.savez(
        calib_path,
        mtx_left=np.eye(3),
        mtx_right=np.eye(3),
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[1.0], [0.0], [0.0]]),
        img_size=np.array([1280, 720]),
        quality_rating="GOOD",
        rms_error_px=0.42,
    )

    status = describe_runtime_calibration(calib_path=calib_path, config_path=tmp_path / "missing.yaml")

    assert status["ok"] is True
    assert status["mode"] == "full_matrix"
    assert status["quality_rating"] == "GOOD"
    assert status["rms_error_px"] == 0.42


def test_describe_runtime_calibration_invalid_matrix_file(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    np.savez(calib_path, mtx_left=np.eye(3))

    status = describe_runtime_calibration(calib_path=calib_path, config_path=tmp_path / "missing.yaml")

    assert status["ok"] is False
    assert status["mode"] == "invalid_matrix_file"
    assert "missing matrix data" in status["message"]


def test_describe_runtime_calibration_scalar_fallback(tmp_path) -> None:
    config_path = tmp_path / "default.yaml"
    config_path.write_text(
        yaml.safe_dump({"stereo": {"baseline_ft": 1.625, "focal_length_px": 1200.0}}),
        encoding="utf-8",
    )

    status = describe_runtime_calibration(calib_path=tmp_path / "missing.npz", config_path=config_path)

    assert status["ok"] is True
    assert status["mode"] == "scalar_fallback"
    assert status["baseline_ft"] == 1.625


def test_describe_runtime_calibration_missing(tmp_path) -> None:
    status = describe_runtime_calibration(calib_path=tmp_path / "missing.npz", config_path=tmp_path / "missing.yaml")

    assert status["ok"] is False
    assert status["mode"] == "missing"
