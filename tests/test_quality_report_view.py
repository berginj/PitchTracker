"""Tests for the Qt-free quality-report view-model (ui.setup.quality_report_view)."""

from __future__ import annotations

import json
from pathlib import Path

from contracts.setup import QUALITY_GRADE_EXCELLENT, QUALITY_GRADE_FAIL
from ui.setup.quality_report_view import (
    load_calibration_quality_report,
    present_quality_report,
)


def _write_report(calib_dir: Path, **metrics) -> None:
    calib_dir.mkdir(parents=True, exist_ok=True)
    (calib_dir / "report.json").write_text(json.dumps(metrics), encoding="utf-8")


def test_load_returns_fail_when_no_metrics_file(tmp_path):
    report = load_calibration_quality_report(tmp_path / "calibration")
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False
    assert any("Run calibration first" in w for w in report.warnings)


def test_load_returns_fail_on_corrupt_metrics_file(tmp_path):
    calib_dir = tmp_path / "calibration"
    calib_dir.mkdir(parents=True)
    (calib_dir / "report.json").write_text("{not json", encoding="utf-8")
    report = load_calibration_quality_report(calib_dir)
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False


def test_load_grades_good_calibration_and_converts_baseline(tmp_path):
    calib_dir = tmp_path / "calibration"
    _write_report(calib_dir, rms_error_px=0.3, baseline_ft=0.75, calibration_mode="FULL")
    report = load_calibration_quality_report(calib_dir)
    assert report.grade == QUALITY_GRADE_EXCELLENT
    assert report.passed is True
    assert abs(report.baseline_in - 9.0) < 1e-6  # 0.75 ft -> 9 in
    assert any("Epipolar error is not measured" in w for w in report.warnings)


def test_load_flags_quick_mode_as_not_production_ready(tmp_path):
    calib_dir = tmp_path / "calibration"
    _write_report(calib_dir, rms_error_px=0.4, baseline_ft=0.7, calibration_mode="QUICK")
    report = load_calibration_quality_report(calib_dir)
    assert any("Quick calibration is diagnostic-only" in w for w in report.warnings)


def test_load_fails_on_poor_rms(tmp_path):
    calib_dir = tmp_path / "calibration"
    _write_report(calib_dir, rms_error_px=4.0, baseline_ft=0.7, calibration_mode="FULL")
    report = load_calibration_quality_report(calib_dir)
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False


def test_present_formats_rows_and_tone(tmp_path):
    calib_dir = tmp_path / "calibration"
    _write_report(calib_dir, rms_error_px=0.3, baseline_ft=0.75, calibration_mode="FULL")
    view = present_quality_report(load_calibration_quality_report(calib_dir))

    assert view.headline == "Calibration quality: EXCELLENT"
    assert view.tone == "success"
    labels = {row.label: row.value for row in view.rows}
    assert labels["RMS reprojection error"] == "0.30 px"
    assert labels["Epipolar error"] == "not measured"
    assert labels["Baseline"] == "9.00 in"
    assert labels["Result"] == "PASS"
    result_row = next(r for r in view.rows if r.label == "Result")
    assert result_row.tone == "success"


def test_present_marks_failed_result_row():
    report = load_calibration_quality_report(Path("does/not/exist"))
    view = present_quality_report(report)
    assert view.tone == "error"
    result_row = next(r for r in view.rows if r.label == "Result")
    assert result_row.value == "FAIL"
    assert result_row.tone == "error"
