"""Physics-based trajectory fitter (ballistic + drag)."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from contracts import StereoObservation, TrackSample
from trajectory.base import TrajectoryFitterBase
from trajectory.confidence import ConfidenceScorer
from trajectory.contracts import (
    FailureCode,
    ResidualReport,
    TrajectoryDiagnostics,
    TrajectoryFitRequest,
    TrajectoryFitResult,
)

try:
    from scipy.optimize import least_squares
except Exception:  # pragma: no cover - handled at runtime
    least_squares = None


GRAVITY_FT_S2 = -32.174


class PhysicsDragFitter(TrajectoryFitterBase):
    def __init__(self) -> None:
        super().__init__()
        self._scorer = ConfidenceScorer()

    def maybe_fit(self) -> Optional[TrajectoryFitResult]:
        if self._request is None or len(self._buffer) < 6:
            return None
        return self._fit(self._request, self._buffer, realtime=True)

    def finalize_fit(self) -> TrajectoryFitResult:
        if self._request is None:
            raise RuntimeError("No request set.")
        return self._fit(self._request, self._buffer, realtime=self._request.realtime)

    def fit_trajectory(self, request: TrajectoryFitRequest) -> TrajectoryFitResult:
        return self._fit(request, request.observations, realtime=request.realtime)

    def _fit(
        self,
        request: TrajectoryFitRequest,
        observations: List[StereoObservation],
        realtime: bool,
    ) -> TrajectoryFitResult:
        diagnostics = TrajectoryDiagnostics()
        if len(observations) < 4:
            diagnostics.failure_codes.append(FailureCode.INSUFFICIENT_POINTS)
            return TrajectoryFitResult(
                model_name="physics_drag",
                samples=[],
                plate_crossing_xyz_ft=None,
                plate_crossing_t_ns=None,
                expected_plate_error_ft=None,
                confidence=0.0,
                diagnostics=diagnostics,
            )
        if least_squares is None:
            diagnostics.failure_codes.append(FailureCode.OPT_DID_NOT_CONVERGE)
            diagnostics.notes.append("scipy unavailable")
            return TrajectoryFitResult(
                model_name="physics_drag",
                samples=[],
                plate_crossing_xyz_ft=None,
                plate_crossing_t_ns=None,
                expected_plate_error_ft=None,
                confidence=0.0,
                diagnostics=diagnostics,
            )

        obs_sorted = sorted(observations, key=lambda obs: obs.t_ns)
        times_s = np.array([(obs.t_ns - obs_sorted[0].t_ns) / 1e9 for obs in obs_sorted])
        positions = np.array([[obs.X, obs.Y, obs.Z] for obs in obs_sorted])
        max_gap_ms = float(np.max(np.diff(times_s)) * 1000.0) if len(times_s) > 1 else 0.0

        seed_state = _seed_state(times_s, positions)
        k0 = request.drag_k0
        dt_seed = (request.fiducial_time_offset_ns or 0) / 1e9
        params0 = np.array(
            [seed_state[0], seed_state[1], seed_state[2], seed_state[3], seed_state[4], seed_state[5], k0, dt_seed],
            dtype=float,
        )

        bounds = (
            np.array(
                [-100.0, -10.0, -10.0, -200.0, -200.0, -400.0, 0.0, -request.time_offset_bounds_ms / 1000.0],
                dtype=float,
            ),
            np.array(
                [100.0, 10.0, 200.0, 200.0, 200.0, 400.0, 0.3, request.time_offset_bounds_ms / 1000.0],
                dtype=float,
            ),
        )

        max_iter = 20 if realtime else request.max_iter
        result = least_squares(
            lambda params: _residuals(
                params=params,
                times_s=times_s,
                positions=positions,
                k0=request.drag_k0,
                sigma_k=request.drag_sigma,
                dt0=dt_seed,
                sigma_dt=request.time_offset_sigma_ms / 1000.0,
                wind=request.wind_ft_s,
            ),
            params0,
            bounds=bounds,
            max_nfev=max_iter,
            loss="huber",
            f_scale=1.5,
        )

        failure_codes = list(diagnostics.failure_codes)
        if not result.success:
            failure_codes.append(FailureCode.OPT_DID_NOT_CONVERGE)

        params = result.x
        samples = _integrate_trajectory(params, times_s, obs_sorted[0].t_ns, request.wind_ft_s)
        plate_crossing = _find_plate_crossing(samples, request.plate_plane_z_ft)
        if plate_crossing is None:
            failure_codes.append(FailureCode.NO_PLATE_CROSSING)
        if not _is_monotonic_z(samples):
            failure_codes.append(FailureCode.NON_MONOTONIC_Z)

        residuals = _build_residual_reports(samples, obs_sorted)
        rmse = _rmse([res.residual_3d_ft for res in residuals if res.residual_3d_ft is not None])
        drag_param = float(params[6])
        drag_param_ok = params[6] >= 0.0
        inlier_ratio = _inlier_ratio(residuals)
        condition_number = _condition_number(result.jac)

        # Build diagnostics with all computed values
        diagnostics = TrajectoryDiagnostics(
            rmse_3d_ft=rmse,
            inlier_ratio=inlier_ratio,
            condition_number=condition_number,
            drag_param=drag_param,
            drag_param_ok=drag_param_ok,
            max_gap_ms=max_gap_ms,
            failure_codes=failure_codes,
            notes=list(diagnostics.notes),
        )

        expected_error = self._scorer.expected_plate_error_ft(
            residual_scale=rmse,
            plate_crossing=plate_crossing,
        )
        confidence = self._scorer.confidence_from_error(expected_error)

        return TrajectoryFitResult(
            model_name="physics_drag",
            samples=samples,
            plate_crossing_xyz_ft=plate_crossing[0] if plate_crossing else None,
            plate_crossing_t_ns=plate_crossing[1] if plate_crossing else None,
            expected_plate_error_ft=expected_error,
            confidence=confidence,
            diagnostics=diagnostics,
            residuals=residuals,
        )


def _seed_state(times_s: np.ndarray, positions: np.ndarray) -> np.ndarray:
    t = times_s - times_s[0]
    X = positions[:, 0]
    Y = positions[:, 1]
    Z = positions[:, 2]
    vx, vy, vz = 0.0, 0.0, 0.0
    if len(t) >= 2:
        vx = (X[-1] - X[0]) / max(t[-1] - t[0], 1e-6)
        vy = (Y[-1] - Y[0]) / max(t[-1] - t[0], 1e-6)
        vz = (Z[-1] - Z[0]) / max(t[-1] - t[0], 1e-6)
    return np.array([X[0], Y[0], Z[0], vx, vy, vz], dtype=float)


def _residuals(
    params: np.ndarray,
    times_s: np.ndarray,
    positions: np.ndarray,
    k0: float,
    sigma_k: float,
    dt0: float,
    sigma_dt: float,
    wind: Optional[Tuple[float, float, float]],
) -> np.ndarray:
    state = params[:6]
    k = params[6]
    dt = params[7]
    residuals = []
    for t, pos in zip(times_s, positions):
        predicted = _propagate(state, t + dt, k, wind)
        residuals.extend(predicted[:3] - pos)
    residuals.append((k - k0) / max(sigma_k, 1e-6))
    residuals.append((dt - dt0) / max(sigma_dt, 1e-6))
    return np.array(residuals, dtype=float)


def _propagate(
    state: np.ndarray,
    t_s: float,
    k: float,
    wind: Optional[Tuple[float, float, float]],
) -> np.ndarray:
    dt = max(t_s, 0.0)
    steps = max(1, int(dt / 0.002))
    h = dt / steps
    x = state.copy()
    wind_vec = np.array(wind, dtype=float) if wind else np.zeros(3, dtype=float)
    for _ in range(steps):
        x = _rk4_step(x, h, k, wind_vec)
    return x


def _rk4_step(state: np.ndarray, h: float, k: float, wind: np.ndarray) -> np.ndarray:
    def dynamics(s: np.ndarray) -> np.ndarray:
        pos = s[:3]
        vel = s[3:]
        rel = vel - wind
        speed = np.linalg.norm(rel)
        drag = -k * speed * rel
        accel = np.array([0.0, GRAVITY_FT_S2, 0.0]) + drag
        return np.concatenate([vel, accel])

    k1 = dynamics(state)
    k2 = dynamics(state + 0.5 * h * k1)
    k3 = dynamics(state + 0.5 * h * k2)
    k4 = dynamics(state + h * k3)
    return state + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def _integrate_trajectory(
    params: np.ndarray,
    times_s: np.ndarray,
    t0_ns: int,
    wind: Optional[Tuple[float, float, float]],
) -> List[TrackSample]:
    state = params[:6]
    k = params[6]
    dt_offset = params[7]
    samples: List[TrackSample] = []
    for t in times_s:
        t_s = t + dt_offset
        t_ns = int(t0_ns + t_s * 1e9)
        predicted = _propagate(state, t_s, k, wind)
        samples.append(
            TrackSample(
                t_ns=t_ns,
                X=float(predicted[0]),
                Y=float(predicted[1]),
                Z=float(predicted[2]),
                Vx=float(predicted[3]),
                Vy=float(predicted[4]),
                Vz=float(predicted[5]),
            )
        )
    return samples


def _find_plate_crossing(
    samples: List[TrackSample],
    plate_z_ft: float,
) -> Optional[Tuple[Tuple[float, float, float], int]]:
    for i in range(len(samples) - 1):
        a = samples[i]
        b = samples[i + 1]
        az = a.Z - plate_z_ft
        bz = b.Z - plate_z_ft
        if az == 0:
            return (a.X, a.Y, a.Z), a.t_ns
        if az * bz <= 0:
            t = az / (az - bz) if (az - bz) != 0 else 0.0
            x = a.X + t * (b.X - a.X)
            y = a.Y + t * (b.Y - a.Y)
            z = a.Z + t * (b.Z - a.Z)
            t_ns = int(a.t_ns + t * (b.t_ns - a.t_ns))
            return (x, y, z), t_ns
    return None


def _build_residual_reports(
    samples: List[TrackSample],
    observations: List[StereoObservation],
) -> List[ResidualReport]:
    residuals: List[ResidualReport] = []
    for obs in observations:
        closest = min(samples, key=lambda s: abs(s.t_ns - obs.t_ns))
        dx = closest.X - obs.X
        dy = closest.Y - obs.Y
        dz = closest.Z - obs.Z
        dist = float((dx * dx + dy * dy + dz * dz) ** 0.5)
        residuals.append(ResidualReport(t_ns=obs.t_ns, residual_3d_ft=dist, normalized_residual=dist))
    return residuals


def _rmse(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return float((sum(v * v for v in vals) / len(vals)) ** 0.5)


def _inlier_ratio(residuals: List[ResidualReport]) -> Optional[float]:
    if not residuals:
        return None
    inliers = [res for res in residuals if res.normalized_residual is not None and res.normalized_residual < 1.0]
    return len(inliers) / len(residuals)


def _condition_number(jacobian: Optional[np.ndarray]) -> Optional[float]:
    if jacobian is None or jacobian.size == 0:
        return None
    try:
        return float(np.linalg.cond(jacobian))
    except np.linalg.LinAlgError:
        return None


def _is_monotonic_z(samples: List[TrackSample]) -> bool:
    if len(samples) < 2:
        return True
    diffs = [samples[i + 1].Z - samples[i].Z for i in range(len(samples) - 1)]
    if all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs):
        return True
    return False
