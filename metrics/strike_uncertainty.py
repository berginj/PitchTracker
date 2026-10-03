"""Conditional strike-boundary sensitivity; never a physical confidence interval."""

from dataclasses import dataclass
from math import sqrt
from typing import Sequence

import numpy as np

from contracts import StereoObservation
from contracts.timing import TimestampEvidence


@dataclass(frozen=True)
class StrikeSensitivity:
    radius_ft: float = 0.0
    reason: str | None = None
    invalid_reason: str | None = None
    basis: str = "piecewise_linear_swept_sphere_conditional_sensitivity"


def strike_sensitivity(
    observations: Sequence[StereoObservation], timing: TimestampEvidence | None,
) -> StrikeSensitivity:
    """Use declared covariance and acquisition uncertainty as sensitivity inputs.

    Three times the largest positional standard deviation is an engineering
    sensitivity band, not a probabilistic interval. Calibration, correlated
    errors and omitted forces remain excluded. Unknown inputs stay explicit.
    """
    if any(type(obs.t_ns) is not int for obs in observations):
        return StrikeSensitivity(invalid_reason="INVALID_TIMESTAMPS")
    if any(b.t_ns <= a.t_ns for a, b in zip(observations, observations[1:])):
        return StrikeSensitivity(invalid_reason="INVALID_TIMESTAMPS")
    spatial = 0.0
    covariance_unknown = False
    for observation in observations:
        if observation.covariance is None:
            covariance_unknown = True
            continue
        try:
            matrix = np.asarray(observation.covariance, dtype=float)
            if (matrix.shape != (3, 3) or not np.all(np.isfinite(matrix))
                    or not np.allclose(matrix, matrix.T, atol=1e-12, rtol=1e-8)):
                return StrikeSensitivity(invalid_reason="INVALID_COVARIANCE")
            eigenvalues = np.linalg.eigvalsh(matrix)
            if eigenvalues.min() < -1e-10:
                return StrikeSensitivity(invalid_reason="INVALID_COVARIANCE")
            spatial = max(spatial, 3.0 * sqrt(max(float(eigenvalues.max()), 0.0)))
        except (ValueError, TypeError, np.linalg.LinAlgError):
            return StrikeSensitivity(invalid_reason="INVALID_COVARIANCE")
    timing_unknown = timing is None or not timing.acquisition_verified
    uncertainty_ns = timing.acquisition_uncertainty_ns if timing is not None else None
    speeds = [
        sqrt((b.X - a.X)**2 + (b.Y - a.Y)**2 + (b.Z - a.Z)**2) * 1e9 / (b.t_ns - a.t_ns)
        for a, b in zip(observations, observations[1:])
    ]
    if uncertainty_ns and not speeds:
        return StrikeSensitivity(invalid_reason="TIMING_SENSITIVITY_UNAVAILABLE")
    motion = max(speeds, default=0.0) * (uncertainty_ns or 0) / 1e9
    unknowns = []
    if covariance_unknown:
        unknowns.append("COVARIANCE_UNKNOWN")
    if timing_unknown:
        unknowns.append("ACQUISITION_TIMING_UNKNOWN")
    return StrikeSensitivity(spatial + motion, "+".join(unknowns) or None)
