"""Tests for quality provenance and versioned error budgets."""

from __future__ import annotations

import pytest

from app.monitoring.error_budget import ErrorBudget, MetricLimit
from contracts import (
    CorrectionRecord,
    MeasurementEvidence,
    QualityAssessment,
    QUALITY_DEGRADED,
    QUALITY_ESTIMATED,
    QUALITY_REJECTED,
    QUALITY_UNAVAILABLE,
    QUALITY_VALIDATED,
)


def test_measurement_and_correction_round_trip() -> None:
    measurement = MeasurementEvidence(
        measurement_id="pair-skew-1",
        name="pair_skew_ms",
        value=0.75,
        units="ms",
        source="host_receive_timestamp",
        uncertainty=0.2,
        rig_profile_id="rig-1",
    )
    correction = CorrectionRecord(
        correction_id="offset-1",
        correction_type="camera_time_offset",
        algorithm="ray_reprojection",
        algorithm_version="1",
        trigger_reason="PAIR_SKEW_BIAS",
        status="APPLIED",
        raw_value=0.75,
        corrected_value=0.1,
        uncertainty_before=0.2,
        uncertainty_after=0.15,
    )

    assert MeasurementEvidence.from_payload(measurement.to_payload()) == measurement
    assert CorrectionRecord.from_payload(correction.to_payload()) == correction


def test_validated_requires_ground_truth_dataset() -> None:
    with pytest.raises(ValueError, match="validation_dataset_id"):
        QualityAssessment("qa-1", "pitch", QUALITY_VALIDATED)

    with pytest.raises(ValueError, match="validation_dataset_id"):
        MeasurementEvidence("m-1", "speed", 80.0, "mph", "vision", status=QUALITY_VALIDATED)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.25, QUALITY_ESTIMATED), (0.75, QUALITY_DEGRADED), (1.5, QUALITY_REJECTED)],
)
def test_error_budget_classifies_upper_bound_metric(value: float, expected: str) -> None:
    budget = ErrorBudget(
        budget_id="capture-v1",
        version="1",
        limits={"pair_skew_ms": MetricLimit(warn=0.5, reject=1.0, units="ms")},
    )

    assessment = budget.assess(
        "stereo_pair",
        {"pair_skew_ms": value},
        assessment_id="pair-1",
    )

    assert assessment.status == expected
    assert assessment.diagnostics["budget_id"] == "capture-v1"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, "not-a-number"])
def test_error_budget_rejects_invalid_metrics(value) -> None:
    budget = ErrorBudget("capture-v1", "1", {"drop_rate": MetricLimit(0.01, 0.05, "ratio")})

    assessment = budget.assess("capture", {"drop_rate": value}, assessment_id="capture-1")

    assert assessment.status == QUALITY_REJECTED
    assert assessment.reason_codes == ["DROP_RATE_INVALID"]


def test_error_budget_does_not_treat_missing_evidence_as_healthy() -> None:
    budget = ErrorBudget("capture-v1", "1", {"drop_rate": MetricLimit(0.01, 0.05, "ratio")})

    assessment = budget.assess("capture", {}, assessment_id="capture-1")

    assert assessment.status == QUALITY_UNAVAILABLE
    assert assessment.reason_codes == ["DROP_RATE_UNAVAILABLE"]
