from __future__ import annotations

import pytest

import pytest

from calib.ground_truth import (
    AcceptanceThresholds,
    ValidationCase,
    ValidationMetadata,
    summarize_validation,
)
from app.monitoring.rig_drift import RigDriftMonitor
from contracts import Detection, QualityAssessment
from trajectory.mode_validation import ModeResult, compare_modes
from trajectory.tracklets import TrackletBuilder
from ui.coaching.diagnostics_view import present_quality


def _detection(u: float, t_ns: int) -> Detection:
    return Detection(
        camera_id="left",
        frame_index=t_ns // 20_000_000,
        t_capture_monotonic_ns=t_ns,
        u=u,
        v=10.0,
        radius_px=3.0,
        confidence=0.9,
    )


def test_tracklets_require_temporally_consistent_candidates() -> None:
    builder = TrackletBuilder(max_speed_px_s=100.0, max_gap_frames=1)
    first = builder.update("left", [_detection(0.0, 0)])
    second = builder.update("left", [_detection(1.0, 20_000_000)])
    assert len(first) == 1
    assert len(second[0].detections) == 2
    # A physically impossible jump starts a distinct tracklet.
    third = builder.update("left", [_detection(100.0, 40_000_000)])
    assert len(third) == 2


def test_drift_monitor_uses_hysteresis_before_state_changes() -> None:
    monitor = RigDriftMonitor(
        "skew", warn_threshold=2.0, fail_threshold=4.0, recovery_threshold=1.0,
        window_size=2, required_bad_windows=2,
    )
    monitor.update(5.0)
    assert monitor.update(5.0).state == "FAIL"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_drift_monitor_rejects_invalid_samples(value: float) -> None:
    monitor = RigDriftMonitor(
        "skew", warn_threshold=2.0, fail_threshold=4.0, recovery_threshold=1.0
    )
    with pytest.raises(ValueError, match="finite and non-negative"):
        monitor.update(value)


def test_mode_comparison_never_promotes_without_ground_truth() -> None:
    report = compare_modes(
        {
            "stereo_3d": ModeResult("stereo_3d", True, (0.0, 2.0, 0.0), 80.0, 0.1, 0.2),
            "ray_graph": ModeResult("ray_graph", True, (0.1, 2.0, 0.0), 81.0, 0.05, 0.1),
        },
        primary_mode="stereo_3d",
    )
    assert report["promotion_decision"] == "REQUIRES_GROUND_TRUTH"


def test_ground_truth_claim_requires_metadata_and_predeclared_thresholds() -> None:
    cases = [ValidationCase("p1", 80.0, 80.5, (0.0, 2.0), (0.02, 2.01), True)]
    unqualified = summarize_validation(cases, dataset_id="dataset-1")
    assert unqualified["claim_ready"] is False
    qualified = summarize_validation(
        cases,
        dataset_id="dataset-1",
        metadata=ValidationMetadata("rig-1", "1.2.3", "indoor fixture"),
        thresholds=AcceptanceThresholds(1, 0.0, 1.0, 1.0, 0.1),
    )
    assert qualified["diagnostic_thresholds_passed"] is True
    assert qualified["claim_ready"] is False
    assert "LEGACY_GROUND_TRUTH_SCHEMA" in qualified["claim_blockers"]


def test_ground_truth_rejects_empty_dataset_and_case_ids() -> None:
    case = ValidationCase("p1", 80.0, 80.0, (0.0, 2.0), (0.0, 2.0), True)
    with pytest.raises(ValueError, match="dataset_id"):
        summarize_validation([case], dataset_id="   ")
    with pytest.raises(ValueError, match="case_id"):
        ValidationCase(" ", 80.0, 80.0, (0.0, 2.0), (0.0, 2.0), True)


def test_ground_truth_rejects_duplicate_case_ids() -> None:
    cases = [
        ValidationCase("p1", 80.0, 80.0, (0.0, 2.0), (0.0, 2.0), True),
        ValidationCase(" p1 ", 81.0, 81.0, (0.0, 2.0), (0.0, 2.0), True),
    ]
    with pytest.raises(ValueError, match="unique"):
        summarize_validation(cases, dataset_id="dataset-1")


def test_coaching_details_are_collapsed_and_unavailable_hides_measurements() -> None:
    assessment = QualityAssessment("q1", "pitch", "UNAVAILABLE", recommendations=["Run setup"])
    view = present_quality(assessment)
    assert view.detail_rows == ()
    assert view.show_measurements is False
    assert view.primary_action == "Run setup"
