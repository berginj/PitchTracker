"""Quality diagnostics for the pipeline orchestrator.

Builds the runtime quality assessment from capture, detection, recording,
and analysis service statistics. Extracted from PipelineOrchestrator to keep
that file under 500 lines.
"""

from __future__ import annotations

from typing import Optional

from app.monitoring.error_budget import ErrorBudget, MetricLimit
from app.services.rig_profile import RigProfile
from contracts import (
    QualityAssessment,
    QUALITY_DEGRADED,
    QUALITY_REJECTED,
    QUALITY_UNAVAILABLE,
)
from log_config.logger import get_logger

logger = get_logger(__name__)


def build_quality_diagnostics(
    capture_stats: dict,
    detection_diagnostics: dict,
    recording_stats: dict,
    analysis_stats: dict,
    profile: Optional[RigProfile],
    calibration_report: Optional[dict],
) -> dict:
    """Assemble the full quality-diagnostics payload.

    All arguments are plain dicts or service stat snapshots so the caller
    can gather them under its own lock and hand them off without holding
    the lock during computation.
    """
    recording = dict(recording_stats)
    analysis = dict(analysis_stats)

    recording_drop = _rate_evidence(
        recording.get("dropped", 0),
        recording.get("submitted", 0) + recording.get("dropped", 0),
    )
    recording_failure = _rate_evidence(
        recording.get("failed", 0), recording.get("submitted", 0)
    )
    analysis_drop = _rate_evidence(
        analysis.get("dropped", 0),
        analysis.get("submitted", 0) + analysis.get("dropped", 0),
    )
    analysis_failure = _rate_evidence(
        analysis.get("failed", 0), analysis.get("submitted", 0)
    )
    recording.update(
        drop_rate=recording_drop["value"],
        drop_rate_evidence=recording_drop,
        failure_rate=recording_failure["value"],
        failure_rate_evidence=recording_failure,
    )
    analysis.update(
        drop_rate=analysis_drop["value"],
        drop_rate_evidence=analysis_drop,
        failure_rate=analysis_failure["value"],
        failure_rate_evidence=analysis_failure,
    )

    pair_rates = (
        (detection_diagnostics.get("pair_outcomes") or {}).get(
            "rejection_rates"
        )
        or {}
    )
    metrics = {
        "detection_loss_rate": (
            detection_diagnostics.get("detection_loss") or {}
        ).get("value"),
        "recording_drop_rate": recording.get("drop_rate"),
        "recording_failure_rate": recording.get("failure_rate"),
        "analysis_drop_rate": analysis.get("drop_rate"),
        "analysis_failure_rate": analysis.get("failure_rate"),
        "pair_skew_p95_ms": (detection_diagnostics.get("sync") or {}).get(
            "p95_delta_ms"
        ),
        "tracklet_start_rate": (
            detection_diagnostics.get("detection") or {}
        ).get("tracklet_start_rate"),
        "pair_skew_rejection_rate": pair_rates.get(
            "PAIR_SKEW_OUT_OF_TOLERANCE"
        ),
        "association_rejection_rate": pair_rates.get(
            "NO_VALID_STEREO_ASSOCIATION"
        ),
    }

    budget = _runtime_error_budget(profile)
    budget_assessment = budget.assess(
        "session", metrics, assessment_id="runtime-current"
    )
    reasons = list(budget_assessment.reason_codes)
    status = budget_assessment.status

    sync_quality = str(
        (detection_diagnostics.get("sync") or {}).get("sync_quality")
        or "UNKNOWN"
    )
    if sync_quality == "POOR":
        status = QUALITY_REJECTED
        reasons.append("STEREO_SYNC_POOR")
    elif sync_quality == "WARN" and status not in {
        QUALITY_REJECTED,
        QUALITY_UNAVAILABLE,
    }:
        status = QUALITY_DEGRADED
        reasons.append("STEREO_SYNC_WARN")
    elif sync_quality == "UNKNOWN" and status != QUALITY_REJECTED:
        status = QUALITY_UNAVAILABLE
        reasons.append("STEREO_SYNC_UNKNOWN")

    drift_state = str(
        (detection_diagnostics.get("drift") or {}).get("state") or "PASS"
    )
    if drift_state == "FAIL":
        status = QUALITY_REJECTED
        reasons.append("RIG_DRIFT_FAIL")
    elif drift_state == "WARN" and status != QUALITY_REJECTED:
        status = QUALITY_DEGRADED
        reasons.append("RIG_DRIFT_WARN")

    assessment = QualityAssessment(
        assessment_id="runtime-current",
        scope="session",
        status=status,
        reason_codes=reasons,
        metrics=metrics,
        thresholds=budget_assessment.thresholds,
        recommendations=(
            ["Open diagnostics and rerun the failing setup check."]
            if reasons
            else []
        ),
        diagnostics=budget_assessment.diagnostics,
    )

    return {
        "quality": assessment.to_payload(),
        "rig_profile_id": profile.profile_id if profile else None,
        "capture": capture_stats,
        "detection": detection_diagnostics,
        "recording": recording,
        "analysis": analysis,
        "calibration": dict(calibration_report or {}),
    }


def _runtime_error_budget(profile: Optional[RigProfile]) -> ErrorBudget:
    """Build the runtime error budget from the rig profile (or defaults)."""
    raw = profile.error_budget if profile is not None else {}
    raw_limits = raw.get("limits") or {}
    limits: dict[str, MetricLimit] = {
        "detection_loss_rate": MetricLimit(0.001, 0.01, "ratio"),
        "recording_drop_rate": MetricLimit(0.001, 0.01, "ratio"),
        "recording_failure_rate": MetricLimit(0.0, 0.01, "ratio"),
        "analysis_drop_rate": MetricLimit(0.0, 0.01, "ratio"),
        "analysis_failure_rate": MetricLimit(0.0, 0.01, "ratio"),
        "pair_skew_p95_ms": MetricLimit(0.5, 1.0, "ms"),
        "tracklet_start_rate": MetricLimit(0.5, 0.8, "ratio"),
        "pair_skew_rejection_rate": MetricLimit(0.01, 0.05, "ratio"),
        "association_rejection_rate": MetricLimit(0.2, 0.5, "ratio"),
    }
    for name, descriptor in raw_limits.items():
        try:
            limits[name] = MetricLimit(
                warn=float(descriptor["warn"]),
                reject=float(descriptor["reject"]),
                units=str(descriptor.get("units") or ""),
            )
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "Ignoring malformed runtime error-budget limit: %s", name
            )
    return ErrorBudget(
        budget_id=str(raw.get("budget_id") or "runtime-default-v2"),
        version=str(raw.get("version") or "2"),
        limits=limits,
    )


def _rate_evidence(numerator: object, denominator: object) -> dict:
    """Return an auditable rate, preserving zero opportunity as unavailable."""
    try:
        if not isinstance(numerator, (str, bytes, int, float)):
            raise TypeError("numerator is not numeric")
        if not isinstance(denominator, (str, bytes, int, float)):
            raise TypeError("denominator is not numeric")
        numerator_value = int(numerator)
        denominator_value = int(denominator)
    except (TypeError, ValueError):
        return {
            "numerator": numerator,
            "denominator": denominator,
            "value": None,
        }
    return {
        "numerator": numerator_value,
        "denominator": denominator_value,
        "value": (
            numerator_value / denominator_value
            if denominator_value > 0
            else None
        ),
    }
