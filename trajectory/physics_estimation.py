"""Weighted stereo estimation and conditional identifiability diagnostics."""

from typing import Any

import numpy as np

from trajectory.contracts import TrajectoryFitRequest


def stationary_track(request: TrajectoryFitRequest) -> bool:
    """Repeated identical positions cannot identify a pitched-ball velocity."""
    if request.mode != "stereo_3d" or len(request.observations) < 4:
        return False
    first = request.observations[0]
    return all((obs.X, obs.Y, obs.Z) == (first.X, first.Y, first.Z) for obs in request.observations)


def observation_whiteners(request: TrajectoryFitRequest) -> tuple[np.ndarray, str]:
    matrices = []
    assumed = 0
    for obs in sorted(request.observations, key=lambda item: item.t_ns):
        covariance = np.asarray(obs.covariance, dtype=float) if obs.covariance is not None else None
        if covariance is None:
            matrices.append(np.eye(3) / request.observation_sigma_ft)
            assumed += 1
            continue
        if covariance.shape != (3, 3) or not np.all(np.isfinite(covariance)):
            raise ValueError("observation covariance must be a finite 3x3 matrix")
        if not np.allclose(covariance, covariance.T):
            raise ValueError("observation covariance must be symmetric")
        values, vectors = np.linalg.eigh(covariance)
        if values.min() < -1e-10:
            raise ValueError("observation covariance must be positive semidefinite")
        # Legacy depth-only covariances encode unknown lateral variance as zero.
        if np.any(values <= 1e-12):
            assumed += 1
            values = np.where(values <= 1e-12, request.observation_sigma_ft**2, values)
        matrices.append((vectors / np.sqrt(values)) @ vectors.T)
    return np.asarray(matrices), "assumed_or_partial" if assumed else "observation_covariance"


def estimate_parameters(request, times_s, positions, seed_state, least_squares_fn, residuals_fn):
    whiteners, basis = observation_whiteners(request)
    # Absolute clock translation trades exactly against initial state. Estimate
    # the state at the first timestamp instead of fitting an unobservable offset.
    initial = np.r_[seed_state, request.drag_k0]
    lower = np.array([-100.0, -10.0, -10.0, -200.0, -200.0, -400.0, 0.0])
    upper = np.array([100.0, 10.0, 200.0, 200.0, 200.0, 400.0, 0.3])
    initial = np.clip(initial, lower + 1e-9, upper - 1e-9)

    def residuals(parameters):
        return residuals_fn(
            np.r_[parameters, 0.0],
            times_s,
            positions,
            request.drag_k0,
            request.drag_sigma,
            0.0,
            request.time_offset_sigma_ms / 1000.0,
            request.wind_ft_s,
            whiteners=whiteners,
            drag_prior_enabled=request.drag_prior_enabled,
        )

    result = least_squares_fn(
        residuals,
        initial,
        bounds=(lower, upper),
        max_nfev=20 if request.realtime else request.max_iter,
        loss="huber",
        f_scale=1.5,
        x_scale="jac",
    )
    return result, np.r_[result.x, 0.0], whiteners, basis


def conditional_speed_std_mph(result: Any) -> float:
    """Local model-conditional uncertainty, excluding calibration/timing/model error."""
    jacobian = np.asarray(result.jac, dtype=float)
    if np.linalg.matrix_rank(jacobian) < jacobian.shape[1]:
        return float("inf")
    _, singular, vh = np.linalg.svd(jacobian, full_matrices=False)
    covariance = (vh.T / singular**2) @ vh
    velocity = np.asarray(result.x[3:6])
    gradient = np.zeros(len(result.x))
    gradient[3:6] = velocity / max(float(np.linalg.norm(velocity)), 1e-12) * (15 / 22)
    return float(np.sqrt(max(float(gradient @ covariance @ gradient), 0.0)))
