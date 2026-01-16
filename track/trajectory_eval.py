"""Evaluation helpers for trajectory fitting."""

from __future__ import annotations

from typing import Iterable, Optional

from contracts import StereoObservation, TrackSample, TrajectoryFit
from log_config.logger import get_logger

logger = get_logger(__name__)


def log_fit_summary(
    fit: TrajectoryFit,
    observations: Optional[Iterable[StereoObservation]] = None,
) -> None:
    samples = fit.samples
    if not samples:
        logger.info(
            "trajectory.fit_summary model=%s samples=0 confidence=%.3f",
            fit.model_name,
            fit.confidence,
        )
        return
    t_start = samples[0].t_ns
    t_end = samples[-1].t_ns
    duration_ms = (t_end - t_start) / 1e6 if t_end >= t_start else 0.0
    residual = None
    if observations is not None:
        residual = _mean_residual_ft(samples, observations)
    logger.info(
        "trajectory.fit_summary model=%s samples=%d duration_ms=%.2f confidence=%.3f residual_ft=%s",
        fit.model_name,
        len(samples),
        duration_ms,
        fit.confidence,
        f\"{residual:.4f}\" if residual is not None else \"n/a\",
    )


def _mean_residual_ft(
    samples: list[TrackSample],
    observations: Iterable[StereoObservation],
) -> Optional[float]:
    obs_list = list(observations)
    if not obs_list:
        return None
    if not samples:
        return None
    total = 0.0
    count = 0
    for obs in obs_list:
        closest = min(samples, key=lambda s: abs(s.t_ns - obs.t_ns))
        dx = closest.X - obs.X
        dy = closest.Y - obs.Y
        dz = closest.Z - obs.Z
        total += (dx * dx + dy * dy + dz * dz) ** 0.5
        count += 1
    return total / count if count else None


__all__ = ["log_fit_summary"]
