"""Tests for read-only calibration report generation."""

from __future__ import annotations

import numpy as np
import pytest
import yaml

from calib.calibration_report import FAIL, PASS, WARN, build_calibration_report


def _write_config(path, *, width: int = 1280, height: int = 720) -> None:
    path.write_text(yaml.safe_dump({"camera": {"width": width, "height": height}}), encoding="utf-8")


def _write_calibration(
    path,
    *,
    mode: str = "FULL",
    production_ready: bool = True,
    rms: float = 0.4,
    baseline_in: float = 19.5,
    image_size: tuple[int, int] | None = (1280, 720),
    quality: str = "GOOD",
    include_production_metadata: bool = True,
    include_sample_evidence: bool = True,
) -> None:
    baseline_mm = baseline_in * 25.4
    payload = dict(
        mtx_left=np.eye(3),
        mtx_right=np.eye(3),
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[baseline_mm], [0.0], [0.0]]),
        E=np.eye(3),
        F=np.eye(3),
        rms_error_px=rms,
        quality_rating=quality,
    )
    if image_size is not None:
        payload["img_size"] = np.array(image_size)
    if include_production_metadata:
        payload["calibration_mode"] = mode
        payload["production_ready"] = production_ready
    if include_sample_evidence:
        payload["per_image_errors"] = np.array(
            [
                {"combined_rms": 0.3},
                {"combined_rms": 0.5},
            ],
            dtype=object,
        )
    np.savez(path, **payload)


def test_full_production_calibration_passes(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    config_path = tmp_path / "config.yaml"
    _write_calibration(calib_path)
    _write_config(config_path)

    report = build_calibration_report(calib_path, config_path, measured_baseline_in=19.4)

    assert report["status"] == PASS
    assert report["production_ready"] is True
    assert report["metrics"]["baseline_in"] == 19.5
    assert report["checks"]["image_size_matches_config"] is True
    assert report["metrics"]["per_image_error_stats"]["count"] == 2


def test_quick_calibration_fails_production_report(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    _write_calibration(calib_path, mode="QUICK", production_ready=False)

    report = build_calibration_report(calib_path)

    assert report["status"] == FAIL
    assert report["production_ready"] is False
    assert any("Quick calibration" in item for item in report["errors"])


def test_missing_matrix_key_fails(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    np.savez(calib_path, mtx_left=np.eye(3))

    report = build_calibration_report(calib_path)

    assert report["status"] == FAIL
    assert report["checks"]["required_matrix_keys_present"] is False
    assert "mtx_right" in report["checks"]["missing_matrix_keys"]


def test_high_rms_fails(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    _write_calibration(calib_path, rms=3.1)

    report = build_calibration_report(calib_path, max_rms_px=2.0)

    assert report["status"] == FAIL
    assert report["checks"]["rms_within_threshold"] is False
    assert any("RMS reprojection" in item for item in report["errors"])


def test_baseline_mismatch_fails(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    _write_calibration(calib_path, baseline_in=19.5)

    report = build_calibration_report(calib_path, measured_baseline_in=25.0, baseline_tolerance_in=1.0)

    assert report["status"] == FAIL
    assert report["checks"]["baseline_matches_measured"] is False
    assert report["metrics"]["baseline_difference_in"] == 5.5


def test_missing_per_image_errors_warns(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    baseline_mm = 19.5 * 25.4
    np.savez(
        calib_path,
        mtx_left=np.eye(3),
        mtx_right=np.eye(3),
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[baseline_mm], [0.0], [0.0]]),
        E=np.eye(3),
        F=np.eye(3),
        img_size=np.array([1280, 720]),
        calibration_mode="FULL",
        production_ready=True,
        rms_error_px=0.4,
        quality_rating="GOOD",
        num_images_used=12,
    )

    report = build_calibration_report(calib_path)

    assert report["status"] == WARN
    assert report["production_ready"] is True
    assert any("Per-image reprojection" in item for item in report["warnings"])


def test_matrix_complete_legacy_artifact_is_diagnostic_only(tmp_path) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    _write_calibration(calib_path, include_production_metadata=False)

    report = build_calibration_report(calib_path)

    assert report["status"] == FAIL
    assert report["production_ready"] is False
    assert report["metrics"]["calibration_mode"] == "UNKNOWN"
    assert any("diagnostic-only" in item for item in report["errors"])


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"rms": float("nan")}, "RMS reprojection"),
        ({"image_size": None}, "image size metadata"),
        ({"include_sample_evidence": False}, "sample/evidence metadata"),
    ],
)
def test_production_metadata_requires_finite_geometry_evidence(tmp_path, overrides, expected_error) -> None:
    calib_path = tmp_path / "stereo_calibration.npz"
    _write_calibration(calib_path, **overrides)

    report = build_calibration_report(calib_path)

    assert report["status"] == FAIL
    assert report["production_ready"] is False
    assert any(expected_error in item for item in report["errors"])
