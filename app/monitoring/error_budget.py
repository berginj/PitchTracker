"""Versioned error-budget evaluation for runtime quality gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Mapping, Optional

from contracts.quality import (
    QUALITY_DEGRADED,
    QUALITY_ESTIMATED,
    QUALITY_REJECTED,
    QUALITY_UNAVAILABLE,
    QualityAssessment,
)


@dataclass(frozen=True)
class MetricLimit:
    """Upper-bound quality limit for a named metric."""

    warn: float
    reject: float
    units: str

    def __post_init__(self) -> None:
        if self.warn < 0 or self.reject < 0:
            raise ValueError("metric limits must be non-negative")
        if self.warn > self.reject:
            raise ValueError("warn limit must not exceed reject limit")


@dataclass(frozen=True)
class ErrorBudget:
    """Named, versioned set of physically justified quality limits."""

    budget_id: str
    version: str
    limits: Mapping[str, MetricLimit] = field(default_factory=dict)

    def assess(
        self,
        scope: str,
        metrics: Mapping[str, Optional[float]],
        *,
        assessment_id: str,
    ) -> QualityAssessment:
        warnings: list[str] = []
        rejections: list[str] = []
        missing: list[str] = []
        thresholds: dict[str, object] = {}

        for name, limit in self.limits.items():
            thresholds[name] = {"warn": limit.warn, "reject": limit.reject, "units": limit.units}
            value = metrics.get(name)
            if value is None:
                missing.append(f"{name.upper()}_UNAVAILABLE")
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                rejections.append(f"{name.upper()}_INVALID")
                continue
            if not isfinite(numeric) or numeric < 0:
                rejections.append(f"{name.upper()}_INVALID")
                continue
            if numeric > limit.reject:
                rejections.append(f"{name.upper()}_EXCEEDS_REJECT_LIMIT")
            elif numeric > limit.warn:
                warnings.append(f"{name.upper()}_EXCEEDS_WARN_LIMIT")

        if rejections:
            status = QUALITY_REJECTED
        elif missing:
            status = QUALITY_UNAVAILABLE
        elif warnings:
            status = QUALITY_DEGRADED
        else:
            status = QUALITY_ESTIMATED

        return QualityAssessment(
            assessment_id=assessment_id,
            scope=scope,
            status=status,
            reason_codes=[*rejections, *missing, *warnings],
            metrics=dict(metrics),
            thresholds=thresholds,
            diagnostics={"budget_id": self.budget_id, "budget_version": self.version},
        )


__all__ = ["ErrorBudget", "MetricLimit"]
