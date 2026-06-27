"""Tests for the Qt-free persist-profile view-model (ui.setup.persist_profile_view)."""

from __future__ import annotations

import json
from pathlib import Path

from contracts.setup import StereoCalibrationProfile
from ui.setup.persist_profile_view import build_stereo_profile_from_report, present_persist_preview


def _write_report(calib_dir: Path, **metrics) -> None:
    calib_dir.mkdir(parents=True, exist_ok=True)
    (calib_dir / "report.json").write_text(json.dumps(metrics), encoding="utf-8")


def _profile(production_ready: bool) -> StereoCalibrationProfile:
    return StereoCalibrationProfile(
        baseline_in=9.0,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.0,
        image_width=1280,
        image_height=720,
        source="charuco" if production_ready else "quick",
        production_ready=production_ready,
        calibration_file="stereo_calibration.npz",
    )


def test_build_profile_from_full_report(tmp_path):
    calib_dir = tmp_path / "calibration"
    _write_report(
        calib_dir,
        rms_error_px=0.3,
        baseline_ft=0.75,
        calibration_mode="FULL",
        image_size=[1280, 720],
    )

    profile = build_stereo_profile_from_report(calib_dir)

    assert profile is not None
    assert profile.production_ready is True
    assert profile.source == "charuco"
    assert profile.baseline_in == 9.0
    assert profile.rms_reprojection_px == 0.3
    assert profile.image_width == 1280
    assert profile.image_height == 720


def test_build_profile_from_quick_report(tmp_path):
    calib_dir = tmp_path / "calibration"
    _write_report(
        calib_dir,
        rms_error_px=0.4,
        baseline_ft=0.7,
        calibration_mode="QUICK",
        image_size=[640, 480],
    )

    profile = build_stereo_profile_from_report(calib_dir)

    assert profile is not None
    assert profile.production_ready is False
    assert profile.source == "quick"
    assert abs(profile.baseline_in - 8.4) < 1e-6


def test_build_profile_returns_none_when_missing(tmp_path):
    assert build_stereo_profile_from_report(tmp_path / "calibration") is None


def test_present_none_profile():
    view = present_persist_preview(None)

    assert view.headline == "No calibration available to persist"
    assert view.tone == "error"
    assert view.rows == []
    assert view.warnings == ["No calibration metrics were found. Run calibration before persisting a profile."]


def test_present_production_ready_profile():
    view = present_persist_preview(_profile(production_ready=True))

    assert view.headline == "Profile ready to persist"
    assert view.tone == "success"
    labels = {row.label: row.value for row in view.rows}
    assert labels["Production ready"] == "yes"
    result_row = next(r for r in view.rows if r.label == "Production ready")
    assert result_row.tone == "success"
    assert view.warnings == []


def test_present_quick_profile():
    view = present_persist_preview(_profile(production_ready=False))

    assert view.headline == "Profile ready to persist"
    assert view.tone == "warning"
    labels = {row.label: row.value for row in view.rows}
    assert labels["Production ready"] == "no"
    assert view.warnings == [
        "This is a diagnostic-only (quick) calibration; it will be saved but is not production-ready."
    ]
