"""Observation health diagnostics for pitch analysis."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from contracts import StereoObservation


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
        }

    duration_ms = (obs[-1].t_ns - obs[0].t_ns) / 1e6 if len(obs) > 1 else 0.0
    rate_hz = (len(obs) / (duration_ms / 1000.0)) if duration_ms > 0.0 else 0.0
    times_s = np.array([item.t_ns for item in obs], dtype=np.float64) / 1e9
    max_gap_ms = float(np.max(np.diff(times_s)) * 1000.0) if len(obs) > 1 else 0.0
    z_values = [item.Z for item in obs]
    confidences = [item.confidence for item in obs]
    return {
        "observation_count": len(obs),
        "observation_duration_ms": float(duration_ms),
        "observation_rate_hz": float(rate_hz),
        "observation_max_gap_ms": max_gap_ms,
        "observation_z_span_ft": float(max(z_values) - min(z_values)),
        "observation_mean_confidence": float(np.mean(confidences)) if confidences else 0.0,
    }
