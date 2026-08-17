"""Durable quality, uncertainty, and correction provenance contracts.

These records distinguish measured evidence from corrected or inferred output.
They are deliberately generic so capture, calibration, tracking, trajectory,
and UI layers can share one vocabulary without sharing mutable state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


SCHEMA_VERSION = "quality.v1"
QUALITY_VALIDATED = "VALIDATED"
QUALITY_ESTIMATED = "ESTIMATED"
QUALITY_DEGRADED = "DEGRADED"
QUALITY_UNAVAILABLE = "UNAVAILABLE"
QUALITY_REJECTED = "REJECTED"
QUALITY_STATUSES = frozenset(
    {
        QUALITY_VALIDATED,
        QUALITY_ESTIMATED,
        QUALITY_DEGRADED,
        QUALITY_UNAVAILABLE,
        QUALITY_REJECTED,
    }
)


class MeasurementStatus(str, Enum):
    """Canonical status vocabulary for pitch measurement claims.

    The enum subclasses ``str`` so existing JSON artifacts and UI consumers
    continue to receive the historical uppercase values during migration.
    """

    VALIDATED = QUALITY_VALIDATED
    ESTIMATED = QUALITY_ESTIMATED
    DEGRADED = QUALITY_DEGRADED
    UNAVAILABLE = QUALITY_UNAVAILABLE
    REJECTED = QUALITY_REJECTED

    @classmethod
    def coerce(cls, value: str | "MeasurementStatus") -> "MeasurementStatus":
        """Convert a persisted/string value to the canonical enum."""
        if isinstance(value, cls):
            return value
        return cls(str(value).upper())


@dataclass(frozen=True)
class MeasurementEvidence:
    """Provenance for a measured or inferred value."""

    measurement_id: str
    name: str
    value: Any
    units: str
    source: str
    timestamp_ns: Optional[int] = None
    uncertainty: Optional[float] = None
    status: str = QUALITY_ESTIMATED
    calibration_id: Optional[str] = None
    rig_profile_id: Optional[str] = None
    validation_dataset_id: Optional[str] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_quality_status(self.status)
        if self.uncertainty is not None and self.uncertainty < 0:
            raise ValueError("uncertainty must be non-negative")
        if self.status == QUALITY_VALIDATED and not self.validation_dataset_id:
            raise ValueError("VALIDATED evidence requires validation_dataset_id")

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "MeasurementEvidence":
        return cls(**dict(payload))


@dataclass(frozen=True)
class CorrectionRecord:
    """Auditable record of one bounded correction attempt."""

    correction_id: str
    correction_type: str
    algorithm: str
    algorithm_version: str
    trigger_reason: str
    status: str
    raw_value: Any = None
    corrected_value: Any = None
    parameters: dict[str, Any] = field(default_factory=dict)
    allowed_range: dict[str, Any] = field(default_factory=dict)
    uncertainty_before: Optional[float] = None
    uncertainty_after: Optional[float] = None
    reason_codes: list[str] = field(default_factory=list)
    timestamp_ns: Optional[int] = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.uncertainty_before is not None and self.uncertainty_before < 0:
            raise ValueError("uncertainty_before must be non-negative")
        if self.uncertainty_after is not None and self.uncertainty_after < 0:
            raise ValueError("uncertainty_after must be non-negative")

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CorrectionRecord":
        return cls(**dict(payload))


@dataclass(frozen=True)
class QualityAssessment:
    """Quality gate result with machine-readable reasons and thresholds."""

    assessment_id: str
    scope: str
    status: str
    reason_codes: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    validation_dataset_id: Optional[str] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_quality_status(self.status)
        if self.status == QUALITY_VALIDATED and not self.validation_dataset_id:
            raise ValueError("VALIDATED assessments require validation_dataset_id")

    @property
    def permits_measurement(self) -> bool:
        return self.status in {QUALITY_VALIDATED, QUALITY_ESTIMATED, QUALITY_DEGRADED}

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QualityAssessment":
        return cls(**dict(payload))


def _require_quality_status(status: str) -> None:
    status_value = status.value if isinstance(status, MeasurementStatus) else status
    if status_value not in QUALITY_STATUSES:
        raise ValueError(f"Unknown quality status: {status}")


__all__ = [
    "CorrectionRecord",
    "MeasurementEvidence",
    "MeasurementStatus",
    "QualityAssessment",
    "QUALITY_DEGRADED",
    "QUALITY_ESTIMATED",
    "QUALITY_REJECTED",
    "QUALITY_STATUSES",
    "QUALITY_UNAVAILABLE",
    "QUALITY_VALIDATED",
]
