"""Ground-truth accuracy reporting that retains failures in denominators."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Iterable, Optional


@dataclass(frozen=True)
class ValidationMetadata:
    rig_profile_id: str
    software_version: str
    environment: str

    def __post_init__(self) -> None:
        if not self.rig_profile_id or not self.software_version or not self.environment:
            raise ValueError("rig profile, software version, and environment are required")


@dataclass(frozen=True)
class AcceptanceThresholds:
    min_samples: int
    max_rejected_rate: float
    max_abs_speed_bias_mph: float
    max_speed_mae_mph: float
    max_plate_mae_ft: float

    def __post_init__(self) -> None:
        if self.min_samples <= 0:
            raise ValueError("min_samples must be positive")
        if not 0.0 <= self.max_rejected_rate <= 1.0:
            raise ValueError("max_rejected_rate must be between zero and one")
        if min(self.max_abs_speed_bias_mph, self.max_speed_mae_mph, self.max_plate_mae_ft) < 0:
            raise ValueError("accuracy thresholds must be non-negative")


@dataclass(frozen=True)
class ValidationCase:
    case_id: str
    expected_speed_mph: Optional[float]
    measured_speed_mph: Optional[float]
    expected_plate_xy_ft: Optional[tuple[float, float]]
    measured_plate_xy_ft: Optional[tuple[float, float]]
    accepted: bool

    def __post_init__(self) -> None:
        if not self.case_id or not self.case_id.strip():
            raise ValueError("validation case_id is required")


def summarize_validation(
    cases: Iterable[ValidationCase],
    *,
    dataset_id: str,
    metadata: Optional[ValidationMetadata] = None,
    thresholds: Optional[AcceptanceThresholds] = None,
) -> dict[str, object]:
    if not dataset_id or not dataset_id.strip():
        raise ValueError("dataset_id is required")
    items = list(cases)
    normalized_case_ids = [item.case_id.strip() for item in items]
    if len(set(normalized_case_ids)) != len(normalized_case_ids):
        raise ValueError("validation case_id values must be unique")
    speed_errors = [
        item.measured_speed_mph - item.expected_speed_mph
        for item in items
        if item.expected_speed_mph is not None and item.measured_speed_mph is not None
    ]
    plate_errors = [
        sqrt(sum((item.measured_plate_xy_ft[i] - item.expected_plate_xy_ft[i]) ** 2 for i in range(2)))
        for item in items
        if item.expected_plate_xy_ft is not None and item.measured_plate_xy_ft is not None
    ]
    rejected = sum(not item.accepted for item in items)
    rejected_rate = rejected / max(len(items), 1)
    speed_bias = mean(speed_errors) if speed_errors else None
    speed_mae = mean(abs(value) for value in speed_errors) if speed_errors else None
    plate_mae = mean(plate_errors) if plate_errors else None
    speed_rmse = sqrt(mean(value * value for value in speed_errors)) if speed_errors else None
    plate_rmse = sqrt(mean(value * value for value in plate_errors)) if plate_errors else None
    coverage_complete = len(speed_errors) == len(items) and len(plate_errors) == len(items)
    checks: dict[str, bool] = {}
    if thresholds is not None:
        checks = {
            "minimum_samples": len(items) >= thresholds.min_samples,
            "rejected_rate": rejected_rate <= thresholds.max_rejected_rate,
            "speed_bias": speed_bias is not None and abs(speed_bias) <= thresholds.max_abs_speed_bias_mph,
            "speed_mae": speed_mae is not None and speed_mae <= thresholds.max_speed_mae_mph,
            "plate_mae": plate_mae is not None and plate_mae <= thresholds.max_plate_mae_ft,
            "coverage_complete": coverage_complete,
        }
    # v1 remains useful for diagnostics and legacy report reads, but it does not
    # bind an independent reference channel, protocol hash, rig revision, or a
    # predeclared tail policy.  Never upgrade it into a physical accuracy claim.
    diagnostic_thresholds_passed = bool(metadata and thresholds and checks and all(checks.values()))
    return {
        "schema_version": "ground_truth_report.v1",
        "dataset_id": dataset_id,
        "sample_count": len(items),
        "accepted_count": len(items) - rejected,
        "rejected_count": rejected,
        "rejected_rate": rejected_rate,
        "speed_evaluated_count": len(speed_errors),
        "speed_bias_mph": speed_bias,
        "speed_mae_mph": speed_mae,
        "speed_rmse_mph": speed_rmse,
        "speed_abs_error_p95_mph": _percentile([abs(value) for value in speed_errors], 0.95),
        "plate_evaluated_count": len(plate_errors),
        "plate_mae_ft": plate_mae,
        "plate_rmse_ft": plate_rmse,
        "plate_error_p95_ft": _percentile(plate_errors, 0.95),
        "metadata": metadata.__dict__ if metadata else None,
        "acceptance_thresholds": thresholds.__dict__ if thresholds else None,
        "acceptance_checks": checks,
        "diagnostic_thresholds_passed": diagnostic_thresholds_passed,
        "accuracy_claim_eligible": False,
        "claim_ready": False,
        "claim_blockers": [
            "LEGACY_GROUND_TRUTH_SCHEMA",
            *(
                [name for name, passed in checks.items() if not passed]
                if metadata and thresholds
                else ["MISSING_VALIDATION_METADATA_OR_THRESHOLDS"]
            ),
        ],
    }


def _percentile(values: list[float], quantile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


__all__ = ["AcceptanceThresholds", "ValidationCase", "ValidationMetadata", "summarize_validation"]
