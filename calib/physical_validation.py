"""Deterministic evaluation of locked, independent physical-validation data."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from math import sqrt
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Optional

from contracts.physical_validation import (
    REPORT_SCHEMA,
    PhysicalValidationDatasetV2,
    PhysicalValidationProtocolV2,
    payload_sha256,
)


REQUIRED_THRESHOLDS = frozenset(
    {
        "max_rejected_rate",
        "max_abs_speed_bias_mph",
        "max_speed_mae_mph",
        "max_speed_tail_error_mph",
        "max_plate_mae_ft",
        "max_plate_tail_error_ft",
        "max_reference_speed_uncertainty_mph",
        "max_reference_plate_uncertainty_ft",
    }
)


def evaluate_physical_validation(
    protocol: PhysicalValidationProtocolV2,
    dataset: PhysicalValidationDatasetV2,
) -> dict[str, Any]:
    """Return a fail-closed v2 report without altering source evidence."""

    blockers: list[str] = []
    if dataset.protocol_sha256 != protocol.protocol_sha256:
        blockers.append("PROTOCOL_HASH_MISMATCH")
    if any(case.mode != protocol.trajectory_mode for case in dataset.cases):
        blockers.append("CASE_TRAJECTORY_MODE_MISMATCH")
    if any(dataset.environment.get(key) != value for key, value in protocol.environment_scope.items()):
        blockers.append("ENVIRONMENT_OUTSIDE_PROTOCOL_SCOPE")
    missing_thresholds = sorted(REQUIRED_THRESHOLDS - set(protocol.thresholds))
    blockers.extend(f"MISSING_THRESHOLD:{name}" for name in missing_thresholds)

    locked_at = _timestamp(protocol.locked_utc)
    if any(_timestamp(case.captured_utc) <= locked_at for case in dataset.cases):
        blockers.append("CASE_CAPTURED_BEFORE_PROTOCOL_LOCK")
    if dataset.phase != "confirmation":
        blockers.append("SHADOW_DATASET_NOT_CLAIM_ELIGIBLE")
    if any(case.used_for_tuning for case in dataset.cases):
        blockers.append("CONFIRMATION_CASE_USED_FOR_TUNING")

    channels = {channel.channel_id: channel for channel in dataset.reference_channels}
    for case in dataset.cases:
        channel = channels[case.reference_channel_id]
        captured = _timestamp(case.captured_utc)
        if not (
            _timestamp(channel.calibration_valid_from_utc)
            <= captured
            <= _timestamp(channel.calibration_valid_until_utc)
        ):
            blockers.append(f"REFERENCE_CALIBRATION_OUT_OF_DATE:{case.case_id}")

    counts = Counter(case.stratum for case in dataset.cases if case.reference_status == "VALID")
    for stratum, minimum in sorted(protocol.planned_strata.items()):
        if counts[stratum] < minimum:
            blockers.append(f"INSUFFICIENT_STRATUM:{stratum}:{counts[stratum]}/{minimum}")

    reference_valid = [case for case in dataset.cases if case.reference_status == "VALID"]
    accepted = [case for case in reference_valid if case.system_outcome == "ACCEPTED"]
    rejected = [case for case in reference_valid if case.system_outcome == "REJECTED"]
    unavailable = [case for case in reference_valid if case.system_outcome == "UNAVAILABLE"]
    rejected_rate = (len(rejected) + len(unavailable)) / len(reference_valid) if reference_valid else None
    if not reference_valid:
        blockers.append("NO_REFERENCE_VALID_OPPORTUNITIES")

    speed_cases = [
        case
        for case in accepted
        if case.reference_speed_mph is not None and case.measured_speed_mph is not None
    ]
    plate_cases = [
        case
        for case in accepted
        if case.reference_plate_xy_ft is not None and case.measured_plate_xy_ft is not None
    ]
    speed_errors = [
        float(case.measured_speed_mph) - float(case.reference_speed_mph)
        for case in speed_cases
        if case.measured_speed_mph is not None and case.reference_speed_mph is not None
    ]
    plate_vectors = []
    for case in plate_cases:
        measured = case.measured_plate_xy_ft
        reference = case.reference_plate_xy_ft
        if measured is not None and reference is not None:
            plate_vectors.append((measured[0] - reference[0], measured[1] - reference[1]))
    plate_errors = [sqrt(x * x + y * y) for x, y in plate_vectors]

    tail_q = protocol.tail_policy.percentile
    speed_tail = _percentile([abs(value) for value in speed_errors], tail_q)
    plate_tail = _percentile(plate_errors, tail_q)
    if "speed" in protocol.claim_scope and len(speed_errors) < protocol.tail_policy.minimum_evaluated_samples:
        blockers.append("INSUFFICIENT_SPEED_TAIL_SAMPLES")
    if "plate_location" in protocol.claim_scope and len(plate_errors) < protocol.tail_policy.minimum_evaluated_samples:
        blockers.append("INSUFFICIENT_PLATE_TAIL_SAMPLES")

    speed_uncertainties = [
        case.reference_speed_uncertainty_mph
        for case in reference_valid
        if case.reference_speed_mph is not None and case.reference_speed_uncertainty_mph is not None
    ]
    plate_uncertainties = [
        case.reference_plate_uncertainty_ft
        for case in reference_valid
        if case.reference_plate_xy_ft is not None and case.reference_plate_uncertainty_ft is not None
    ]
    if "speed" in protocol.claim_scope and len(speed_uncertainties) != sum(
        case.reference_speed_mph is not None for case in reference_valid
    ):
        blockers.append("MISSING_SPEED_REFERENCE_UNCERTAINTY")
    if "plate_location" in protocol.claim_scope and len(plate_uncertainties) != sum(
        case.reference_plate_xy_ft is not None for case in reference_valid
    ):
        blockers.append("MISSING_PLATE_REFERENCE_UNCERTAINTY")

    metrics = {
        "planned_count": sum(protocol.planned_strata.values()),
        "captured_count": len(dataset.cases),
        "reference_valid_count": len(reference_valid),
        "reference_invalid_count": len(dataset.cases) - len(reference_valid),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "unavailable_count": len(unavailable),
        "rejected_or_unavailable_rate": rejected_rate,
        "speed_evaluated_count": len(speed_errors),
        "speed_bias_mph": mean(speed_errors) if speed_errors else None,
        "speed_mae_mph": mean(abs(value) for value in speed_errors) if speed_errors else None,
        "speed_rmse_mph": sqrt(mean(value * value for value in speed_errors)) if speed_errors else None,
        "speed_tail_error_mph": speed_tail,
        "plate_evaluated_count": len(plate_errors),
        "plate_x_bias_ft": mean(value[0] for value in plate_vectors) if plate_vectors else None,
        "plate_y_bias_ft": mean(value[1] for value in plate_vectors) if plate_vectors else None,
        "plate_mae_ft": mean(plate_errors) if plate_errors else None,
        "plate_rmse_ft": sqrt(mean(value * value for value in plate_errors)) if plate_errors else None,
        "plate_tail_error_ft": plate_tail,
        "max_reference_speed_uncertainty_mph": max(speed_uncertainties) if speed_uncertainties else None,
        "max_reference_plate_uncertainty_ft": max(plate_uncertainties) if plate_uncertainties else None,
        "stratum_reference_valid_counts": dict(sorted(counts.items())),
    }

    checks = _threshold_checks(protocol, metrics)
    blockers.extend(name for name, passed in checks.items() if not passed)
    blockers = list(dict.fromkeys(blockers))
    claim_ready = not blockers
    report = {
        "schema_version": REPORT_SCHEMA,
        "protocol_id": protocol.protocol_id,
        "protocol_sha256": protocol.protocol_sha256,
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": dataset.dataset_sha256,
        "dataset_phase": dataset.phase,
        "trajectory_mode": protocol.trajectory_mode,
        "rig_profile_id": dataset.rig_profile_id,
        "rig_profile_revision": dataset.rig_profile_revision,
        "pipeline_fingerprint": dataset.pipeline_fingerprint,
        "claim_scope": list(protocol.claim_scope),
        "tail_policy": protocol.tail_policy.__dict__,
        "metrics": metrics,
        "thresholds": dict(sorted(protocol.thresholds.items())),
        "acceptance_checks": checks,
        "accuracy_claim_eligible": claim_ready,
        "claim_ready": claim_ready,
        "claim_blockers": blockers,
        "correction_policy_sha256": protocol.correction_policy_sha256,
        "note": "Accuracy metrics are conditional on accepted system outcomes; rejection and unavailable rates retain every reference-valid opportunity.",
    }
    report["report_content_sha256"] = payload_sha256(report)
    return report


def validate_physical_validation_files(protocol_path: Path, dataset_path: Path) -> dict[str, Any]:
    protocol = PhysicalValidationProtocolV2.from_payload(_load_object(protocol_path))
    dataset = PhysicalValidationDatasetV2.from_payload(_load_object(dataset_path))
    return evaluate_physical_validation(protocol, dataset)


def _threshold_checks(protocol: PhysicalValidationProtocolV2, metrics: dict[str, Any]) -> dict[str, bool]:
    thresholds = protocol.thresholds
    if REQUIRED_THRESHOLDS - set(thresholds):
        return {}
    checks = {
        "rejected_rate": _upper(metrics["rejected_or_unavailable_rate"], thresholds["max_rejected_rate"]),
    }
    if "speed" in protocol.claim_scope:
        checks.update(
            speed_bias=_absolute(metrics["speed_bias_mph"], thresholds["max_abs_speed_bias_mph"]),
            speed_mae=_upper(metrics["speed_mae_mph"], thresholds["max_speed_mae_mph"]),
            speed_tail=_upper(metrics["speed_tail_error_mph"], thresholds["max_speed_tail_error_mph"]),
            speed_reference_uncertainty=_upper(
                metrics["max_reference_speed_uncertainty_mph"],
                thresholds["max_reference_speed_uncertainty_mph"],
            ),
        )
    if "plate_location" in protocol.claim_scope:
        checks.update(
            plate_mae=_upper(metrics["plate_mae_ft"], thresholds["max_plate_mae_ft"]),
            plate_tail=_upper(metrics["plate_tail_error_ft"], thresholds["max_plate_tail_error_ft"]),
            plate_reference_uncertainty=_upper(
                metrics["max_reference_plate_uncertainty_ft"],
                thresholds["max_reference_plate_uncertainty_ft"],
            ),
        )
    return checks


def _upper(value: Optional[float], threshold: float) -> bool:
    return value is not None and value <= threshold


def _absolute(value: Optional[float], threshold: float) -> bool:
    return value is not None and abs(value) <= threshold


def _percentile(values: Iterable[float], quantile: float) -> Optional[float]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"physical validation JSON must be an object: {path}")
    return payload


__all__ = ["REQUIRED_THRESHOLDS", "evaluate_physical_validation", "validate_physical_validation_files"]
