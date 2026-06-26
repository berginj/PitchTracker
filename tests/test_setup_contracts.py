"""Tests for the typed setup result contracts (contracts.setup)."""

from __future__ import annotations

from contracts.setup import (
    QUALITY_GRADE_GOOD,
    CalibrationQualityReport,
    CoarseRectificationResult,
    ExposureLockResult,
    FocusLockResult,
    StereoCalibrationProfile,
    StereoOverlapResult,
    SyncCheckResult,
)


def _sync() -> SyncCheckResult:
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
        verdict="GOOD",
        passed=True,
    )


def test_focus_lock_payload_round_trips():
    result = FocusLockResult(
        camera_id="left",
        sharpness=120.0,
        sharpness_threshold=80.0,
        autofocus_disabled=True,
        verdict="LOCKED",
        passed=True,
    )
    payload = result.to_payload()
    assert payload["camera_id"] == "left"
    assert payload["autofocus_disabled"] is True
    assert set(payload) == {
        "camera_id",
        "sharpness",
        "sharpness_threshold",
        "autofocus_disabled",
        "verdict",
        "passed",
        "recommendation",
    }


def test_exposure_lock_payload_round_trips():
    result = ExposureLockResult(
        camera_id="right",
        exposure_us=4000.0,
        gain=2.0,
        white_balance_k=4500.0,
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
        readback_verified=True,
        verdict="LOCKED",
        passed=True,
    )
    payload = result.to_payload()
    assert payload["readback_verified"] is True
    assert payload["exposure_us"] == 4000.0


def test_overlap_payload_round_trips():
    result = StereoOverlapResult(
        keypoints_left=500,
        keypoints_right=480,
        raw_matches=300,
        inlier_matches=250,
        inlier_ratio=250 / 300,
        overlap_score=0.7,
        mean_match_distance_px=12.0,
        verdict="GOOD",
        passed=True,
    )
    payload = result.to_payload()
    assert payload["inlier_matches"] == 250
    assert 0.0 <= payload["overlap_score"] <= 1.0


def test_coarse_rectification_payload_serializes_matrices_as_lists():
    f = tuple(float(i) for i in range(9))
    h = tuple(float(i) for i in range(9))
    result = CoarseRectificationResult(
        fundamental_matrix=f,
        left_homography=h,
        right_homography=h,
        epipolar_error_before_px=3.0,
        epipolar_error_after_px=0.4,
        inlier_matches=200,
        converged=True,
        passed=True,
    )
    payload = result.to_payload()
    assert isinstance(payload["fundamental_matrix"], list)
    assert len(payload["fundamental_matrix"]) == 9
    assert payload["epipolar_error_after_px"] < payload["epipolar_error_before_px"]


def test_stereo_calibration_profile_payload():
    profile = StereoCalibrationProfile(
        baseline_in=12.0,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.2,
        image_width=1280,
        image_height=800,
        source="targetless",
        production_ready=False,
    )
    payload = profile.to_payload()
    assert payload["source"] == "targetless"
    assert payload["production_ready"] is False


def test_quality_report_nests_optional_results():
    report = CalibrationQualityReport(
        grade=QUALITY_GRADE_GOOD,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.2,
        baseline_in=12.0,
        passed=True,
        sync=_sync(),
        warnings=["ChArUco fine-tuning skipped"],
    )
    payload = report.to_payload()
    assert payload["grade"] == QUALITY_GRADE_GOOD
    assert payload["sync"]["verdict"] == "GOOD"
    assert payload["overlap"] is None
    assert payload["rectification"] is None
    assert payload["focus_locks"] == []
    assert payload["warnings"] == ["ChArUco fine-tuning skipped"]


def test_quality_report_defaults_are_independent_lists():
    a = CalibrationQualityReport(
        grade="FAIL", rms_reprojection_px=0.0, epipolar_error_px=0.0, baseline_in=0.0, passed=False
    )
    b = CalibrationQualityReport(
        grade="FAIL", rms_reprojection_px=0.0, epipolar_error_px=0.0, baseline_in=0.0, passed=False
    )
    a.warnings.append("x")
    assert b.warnings == []
