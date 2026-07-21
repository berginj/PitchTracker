"""Bounded, auditable corrections for observable setup/runtime errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from contracts import CorrectionRecord


@dataclass(frozen=True)
class TimeOffsetCorrection:
    corrected_timestamp_ns: int
    record: CorrectionRecord


def correct_camera_time_offset(
    timestamp_ns: int,
    estimated_offset_ms: float,
    *,
    max_abs_offset_ms: float,
    uncertainty_before_ms: Optional[float] = None,
    uncertainty_after_ms: Optional[float] = None,
    correction_id: str,
) -> TimeOffsetCorrection:
    """Apply an observed time offset only when it is inside policy bounds."""
    allowed = abs(float(estimated_offset_ms)) <= float(max_abs_offset_ms)
    corrected = timestamp_ns - int(estimated_offset_ms * 1e6) if allowed else timestamp_ns
    status = "APPLIED" if allowed else "REJECTED"
    reasons = [] if allowed else ["TIME_OFFSET_OUTSIDE_ALLOWED_RANGE"]
    record = CorrectionRecord(
        correction_id=correction_id,
        correction_type="camera_time_offset",
        algorithm="bounded_time_offset",
        algorithm_version="1",
        trigger_reason="OBSERVED_CAMERA_TIME_BIAS",
        status=status,
        raw_value={"timestamp_ns": timestamp_ns, "offset_ms": estimated_offset_ms},
        corrected_value={"timestamp_ns": corrected},
        allowed_range={"max_abs_offset_ms": max_abs_offset_ms},
        uncertainty_before=uncertainty_before_ms,
        uncertainty_after=uncertainty_after_ms if allowed else uncertainty_before_ms,
        reason_codes=reasons,
        timestamp_ns=timestamp_ns,
    )
    return TimeOffsetCorrection(corrected, record)


__all__ = ["TimeOffsetCorrection", "correct_camera_time_offset"]


def record_fitted_camera_time_offset(
    estimated_offset_ms: float,
    *,
    prior_offset_ms: float,
    max_abs_offset_ms: float,
    correction_id: str,
    timestamp_ns: Optional[int] = None,
) -> CorrectionRecord:
    """Describe the bounded offset used inside a trajectory fit.

    This does not rewrite capture timestamps. It records the fitter's explicit
    camera-time parameter and whether policy allowed that parameter.
    """
    allowed = abs(float(estimated_offset_ms)) <= float(max_abs_offset_ms)
    return CorrectionRecord(
        correction_id=correction_id,
        correction_type="camera_time_offset",
        algorithm="trajectory_time_offset_parameter",
        algorithm_version="1",
        trigger_reason="FITTER_ESTIMATED_CAMERA_TIME_BIAS",
        status="APPLIED" if allowed else "REJECTED",
        raw_value={"prior_offset_ms": float(prior_offset_ms)},
        corrected_value={"fitted_offset_ms": float(estimated_offset_ms)} if allowed else None,
        parameters={"parameter_scope": "trajectory_fit_only", "capture_timestamps_mutated": False},
        allowed_range={"min_ms": -float(max_abs_offset_ms), "max_ms": float(max_abs_offset_ms)},
        reason_codes=[] if allowed else ["TIME_OFFSET_OUTSIDE_ALLOWED_RANGE"],
        timestamp_ns=timestamp_ns,
    )


__all__.append("record_fitted_camera_time_offset")
