from __future__ import annotations

from app.monitoring.error_budget import ErrorBudget, MetricLimit
from calib.capture_qualification import qualify_capture
from contracts import QUALITY_DEGRADED, QUALITY_ESTIMATED


def _budget() -> ErrorBudget:
    return ErrorBudget(
        "capture-v1",
        "1",
        {
            "pair_skew_p95_ms": MetricLimit(0.5, 1.0, "ms"),
            "frame_drop_rate": MetricLimit(0.01, 0.05, "ratio"),
            "unmatched_frame_rate": MetricLimit(0.02, 0.1, "ratio"),
            "mode_mismatch": MetricLimit(0.0, 0.5, "boolean"),
            "controls_unverified": MetricLimit(0.0, 1.0, "boolean"),
        },
    )


def test_capture_qualification_reports_rates_and_fps() -> None:
    timestamps = [0, 10_000_000, 20_000_000, 30_000_000]
    result = qualify_capture(
        timestamps,
        timestamps,
        [100_000] * 4,
        requested_mode={"fps": 100},
        negotiated_mode={"fps": 100},
        expected_frames=4,
        controls_verified=True,
        budget=_budget(),
        qualification_id="q1",
    )
    assert result.achieved_fps_left == 100.0
    assert result.frame_drop_rate == 0.0
    assert result.assessment.status == QUALITY_ESTIMATED


def test_capture_qualification_degrades_unverified_controls() -> None:
    timestamps = [0, 10_000_000, 20_000_000]
    result = qualify_capture(
        timestamps,
        timestamps,
        [100_000] * 3,
        requested_mode={"fps": 100},
        negotiated_mode={"fps": 100},
        expected_frames=3,
        controls_verified=False,
        budget=_budget(),
        qualification_id="q2",
    )
    assert result.assessment.status == QUALITY_DEGRADED
