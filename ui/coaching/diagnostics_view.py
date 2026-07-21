"""Qt-free progressive-disclosure model for coaching diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from contracts import QualityAssessment, QUALITY_REJECTED, QUALITY_UNAVAILABLE


@dataclass(frozen=True)
class CoachingHealthView:
    headline: str
    status: str
    primary_action: str
    show_measurements: bool
    detail_rows: tuple[tuple[str, str], ...]


def present_quality(assessment: QualityAssessment, *, details_expanded: bool = False) -> CoachingHealthView:
    action = assessment.recommendations[0] if assessment.recommendations else ""
    show_measurements = assessment.status not in {QUALITY_REJECTED, QUALITY_UNAVAILABLE}
    rows: tuple[tuple[str, str], ...] = ()
    if details_expanded:
        rows = tuple((name, str(value)) for name, value in sorted(assessment.metrics.items()))
    headline = {
        "VALIDATED": "System validated",
        "ESTIMATED": "Tracking ready",
        "DEGRADED": "Tracking degraded",
        "UNAVAILABLE": "Measurements unavailable",
        "REJECTED": "Pitch rejected",
    }[assessment.status]
    return CoachingHealthView(headline, assessment.status, action, show_measurements, rows)


__all__ = ["CoachingHealthView", "present_quality"]
