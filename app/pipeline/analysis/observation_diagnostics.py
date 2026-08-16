"""Observation health diagnostics for pitch analysis."""

from __future__ import annotations

from math import isfinite
from typing import Iterable

import numpy as np

from contracts import StereoObservation


MIN_OBSERVATIONS_FOR_QUALITY = 4
MIN_MEAN_CONFIDENCE = 0.35
WARN_MEAN_CONFIDENCE = 0.60
MAX_DEPTH_SIGMA_FT = 8.0
WARN_DEPTH_SIGMA_FT = 4.0
WARN_MAX_GAP_MS = 50.0


def summarize_observations(observations: Iterable[StereoObservation]) -> dict:
    """Summarize timestamp and 3D coverage health for a pitch observation set."""
    obs = sorted(list(observations), key=lambda item: item.t_ns)
    if not obs:
        return {
            "observation_count": 0,
            "observation_duration_ms": 0.0,
            "observation_rate_hz": 0.0,
            "observation_max_gap_ms": 0.0,
            "observation_z_span_ft": 0.0,
            "observation_mean_confidence": 0.0,
            "observation_mean_depth_sigma_ft": None,
            "observation_max_depth_sigma_ft": None,
            "observation_quality_status": "REJECT",
            "observation_rejection_reasons": ["NO_OBSERVATIONS"],
            "observation_warning_reasons": [],
        }

    duration_ms = (obs[-1].t_ns - obs[0].t_ns) / 1e6 if len(obs) > 1 else 0.0
    rate_hz = ((len(obs) - 1) / (duration_ms / 1000.0)) if duration_ms > 0.0 else 0.0
    times_s = np.array([item.t_ns for item in obs], dtype=np.float64) / 1e9
    max_gap_ms = float(np.max(np.diff(times_s)) * 1000.0) if len(obs) > 1 else 0.0
    z_values = [float(item.Z) for item in obs]
    confidences = [item.confidence for item in obs]
    depth_sigmas: list[float] = [
        item for item in (_depth_sigma_ft(observation) for observation in obs) if item is not None
    ]
    quality_status, rejection_reasons, warning_reasons = _observation_quality(
        observation_count=len(obs),
        mean_confidence=float(np.mean(confidences)) if confidences else 0.0,
        max_gap_ms=max_gap_ms,
        max_depth_sigma_ft=float(max(depth_sigmas)) if depth_sigmas else None,
        uncertainty_count=len(depth_sigmas),
    )
    return {
        "observation_count": len(obs),
        "observation_duration_ms": float(duration_ms),
        "observation_rate_hz": float(rate_hz),
        "observation_max_gap_ms": max_gap_ms,
        "observation_z_span_ft": float(max(z_values) - min(z_values)),
        "observation_mean_confidence": float(np.mean(confidences)) if confidences else 0.0,
        "observation_mean_depth_sigma_ft": float(np.mean(depth_sigmas)) if depth_sigmas else None,
        "observation_max_depth_sigma_ft": float(max(depth_sigmas)) if depth_sigmas else None,
        "observation_quality_status": quality_status,
        "observation_rejection_reasons": rejection_reasons,
        "observation_warning_reasons": warning_reasons,
    }


def _depth_sigma_ft(observation: StereoObservation) -> float | None:
    if observation.covariance is None:
        return None
    try:
        variance = float(observation.covariance[2][2])
    except (IndexError, TypeError, ValueError):
        return None
    if not isfinite(variance) or variance < 0.0:
        return None
    return float(variance**0.5)


def _observation_quality(
    *,
    observation_count: int,
    mean_confidence: float,
    max_gap_ms: float,
    max_depth_sigma_ft: float | None,
    uncertainty_count: int,
) -> tuple[str, list[str], list[str]]:
    rejection_reasons: list[str] = []
    warning_reasons: list[str] = []

    if observation_count < MIN_OBSERVATIONS_FOR_QUALITY:
        rejection_reasons.append("INSUFFICIENT_OBSERVATIONS")
    if mean_confidence < MIN_MEAN_CONFIDENCE:
        rejection_reasons.append("LOW_OBSERVATION_CONFIDENCE")
    elif mean_confidence < WARN_MEAN_CONFIDENCE:
        warning_reasons.append("LOW_OBSERVATION_CONFIDENCE")

    if uncertainty_count == 0:
        warning_reasons.append("UNCERTAINTY_UNAVAILABLE")
    elif uncertainty_count < observation_count:
        warning_reasons.append("UNCERTAINTY_EVIDENCE_INCOMPLETE")

    if max_depth_sigma_ft is not None:
        if max_depth_sigma_ft > MAX_DEPTH_SIGMA_FT:
            rejection_reasons.append("HIGH_DEPTH_UNCERTAINTY")
        elif max_depth_sigma_ft > WARN_DEPTH_SIGMA_FT:
            warning_reasons.append("HIGH_DEPTH_UNCERTAINTY")

    if max_gap_ms > WARN_MAX_GAP_MS:
        warning_reasons.append("LARGE_OBSERVATION_GAP")

    if rejection_reasons:
        return "REJECT", rejection_reasons, warning_reasons
    if warning_reasons:
        return "WARN", rejection_reasons, warning_reasons
    return "PASS", rejection_reasons, warning_reasons
