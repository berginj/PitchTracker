"""Tests for the setup quality-report aggregator (step 9)."""

from __future__ import annotations

from calib.stereo_setup.quality_report import build_quality_report
from contracts.setup import (
    QUALITY_GRADE_EXCELLENT,
    QUALITY_GRADE_FAIL,
    QUALITY_GRADE_GOOD,
    QUALITY_GRADE_MARGINAL,
    CoarseRectificationResult,
    ExposureLockResult,
    FocusLockResult,
    StereoOverlapResult,
    SyncCheckResult,
)


def _sync(passed: bool = True) -> SyncCheckResult:
    return SyncCheckResult(
        sample_count=60,
        unpaired_count=0,
        mean_delta_ms=1.0,
        p95_delta_ms=1.2,
        max_delta_ms=1.5,
        jitter_ms=0.3,
        max_motion_in=1.6,
        tolerance_ms=8.0,
        max_speed_mph=60.0,
        verdict="GOOD" if passed else "POOR",
        passed=passed,
        recommendation="" if passed else "Reduce camera jitter.",
    )


def _overlap(passed: bool = True) -> StereoOverlapResult:
    return StereoOverlapResult(
        keypoints_left=400,
        keypoints_right=410,
        raw_matches=200,
        inlier_matches=160,
        inlier_ratio=0.8,
        overlap_score=0.7,
        mean_match_distance_px=2.0,
        verdict="GOOD" if passed else "POOR",
        passed=passed,
    )


def _rectify(passed: bool = True) -> CoarseRectificationResult:
    return CoarseRectificationResult(
        fundamental_matrix=tuple(range(9)),
        left_homography=tuple(range(9)),
        right_homography=tuple(range(9)),
        epipolar_error_before_px=5.0,
        epipolar_error_after_px=0.4,
        inlier_matches=160,
        converged=True,
        passed=passed,
    )


def _focus(camera_id: str, passed: bool = True) -> FocusLockResult:
    return FocusLockResult(
        camera_id=camera_id,
        sharpness=120.0,
        sharpness_threshold=80.0,
        autofocus_disabled=True,
        verdict="LOCKED" if passed else "UNLOCKED",
        passed=passed,
        recommendation="" if passed else "Refocus camera.",
    )


def _exposure(camera_id: str, passed: bool = True) -> ExposureLockResult:
    return ExposureLockResult(
        camera_id=camera_id,
        exposure_us=2000.0,
        gain=1.0,
        white_balance_k=4500.0,
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
        readback_verified=True,
        verdict="LOCKED" if passed else "UNLOCKED",
        passed=passed,
    )


def _all_steps_ok():
    return dict(
        sync=_sync(),
        overlap=_overlap(),
        rectification=_rectify(),
        focus_locks=[_focus("left"), _focus("right")],
        exposure_locks=[_exposure("left"), _exposure("right")],
    )


def test_excellent_grade_when_metrics_tight_and_all_steps_pass():
    report = build_quality_report(
        rms_reprojection_px=0.3,
        epipolar_error_px=0.4,
        baseline_in=8.0,
        **_all_steps_ok(),
    )
    assert report.grade == QUALITY_GRADE_EXCELLENT
    assert report.passed is True
    assert report.warnings == []


def test_good_and_marginal_buckets_track_worse_metric():
    good = build_quality_report(rms_reprojection_px=0.4, epipolar_error_px=0.9, baseline_in=8.0, **_all_steps_ok())
    assert good.grade == QUALITY_GRADE_GOOD

    marginal = build_quality_report(rms_reprojection_px=1.8, epipolar_error_px=0.4, baseline_in=8.0, **_all_steps_ok())
    assert marginal.grade == QUALITY_GRADE_MARGINAL
    assert marginal.passed is True


def test_metric_over_marginal_bound_fails():
    report = build_quality_report(rms_reprojection_px=3.5, epipolar_error_px=0.4, baseline_in=8.0, **_all_steps_ok())
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False


def test_failed_step_forces_fail_even_with_good_metrics():
    steps = _all_steps_ok()
    steps["overlap"] = _overlap(passed=False)
    report = build_quality_report(rms_reprojection_px=0.3, epipolar_error_px=0.3, baseline_in=8.0, **steps)
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False
    assert any("Overlap validation" in w for w in report.warnings)


def test_failed_camera_lock_is_attributed_and_fails():
    steps = _all_steps_ok()
    steps["focus_locks"] = [_focus("left"), _focus("right", passed=False)]
    report = build_quality_report(rms_reprojection_px=0.3, epipolar_error_px=0.3, baseline_in=8.0, **steps)
    assert report.passed is False
    assert any("right" in w and "Focus lock" in w for w in report.warnings)


def test_missing_steps_are_warned_but_metrics_still_grade():
    report = build_quality_report(rms_reprojection_px=0.3, epipolar_error_px=0.3, baseline_in=8.0)
    # No steps run -> not all passed -> FAIL grade with warnings, never silently GOOD.
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False
    assert any("was not run" in w for w in report.warnings)


def test_metrics_only_summary_grades_on_metrics_when_steps_not_required():
    report = build_quality_report(
        rms_reprojection_px=0.3,
        epipolar_error_px=0.3,
        baseline_in=8.0,
        require_steps=False,
    )
    # Metrics-only end-of-setup summary: not-run steps are warnings, not failures.
    assert report.grade == QUALITY_GRADE_EXCELLENT
    assert report.passed is True
    assert any("was not run" in w for w in report.warnings)


def test_metrics_only_summary_still_fails_on_bad_metrics():
    report = build_quality_report(
        rms_reprojection_px=4.0,
        epipolar_error_px=0.3,
        baseline_in=8.0,
        require_steps=False,
    )
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False


def test_metrics_only_summary_still_fails_on_failed_step():
    # Even in metrics-only mode, a step that ran and FAILED must fail the rig.
    report = build_quality_report(
        rms_reprojection_px=0.3,
        epipolar_error_px=0.3,
        baseline_in=8.0,
        require_steps=False,
        overlap=_overlap(passed=False),
    )
    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False


def test_extra_warnings_are_appended_and_payload_serializes():
    report = build_quality_report(
        rms_reprojection_px=0.3,
        epipolar_error_px=0.3,
        baseline_in=8.0,
        extra_warnings=["Quick calibration is diagnostic-only."],
        **_all_steps_ok(),
    )
    assert "Quick calibration is diagnostic-only." in report.warnings
    payload = report.to_payload()
    assert payload["grade"] == QUALITY_GRADE_EXCELLENT
    assert payload["passed"] is True
    assert payload["overlap"]["passed"] is True
    assert isinstance(payload["created_utc"], str) and payload["created_utc"]
