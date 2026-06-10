"""Ray trajectory fitting helpers — propagation, triangulation, and residual utilities."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from contracts import RayObservation, TrackSample
from trajectory.camera_model import RayCameraModel
from trajectory.contracts import (
    ResidualReport,
    TrajectoryDiagnostics,
    TrajectoryFitRequest,
    TrajectoryFitResult,
)
from trajectory.physics import (
    _seed_state,
)

RIGHT_CAMERA_IDS = {"right", "camera_right", "cam_right", "r"}
GRAVITY_FT_S2 = -32.174


def normalize_camera_models(models: Dict[str, RayCameraModel]) -> Dict[str, RayCameraModel]:
    normalized: Dict[str, RayCameraModel] = {}
    for camera_id, model in models.items():
        key = normalize_camera_id(camera_id)
        normalized[key] = model
    return normalized


def rays_with_known_cameras(
    rays: Iterable[RayObservation],
    camera_models: Dict[str, RayCameraModel],
) -> List[RayObservation]:
    normalized = []
    for ray in rays:
        camera_id = normalize_camera_id(ray.camera_id)
        if camera_id not in camera_models:
            continue
        normalized.append(
            RayObservation(
                camera_id=camera_id,
                frame_index=ray.frame_index,
                t_ns=ray.t_ns,
                u=ray.u,
                v=ray.v,
                radius_px=ray.radius_px,
                confidence=ray.confidence,
            )
        )
    return normalized


def normalize_camera_id(camera_id: str) -> str:
    lowered = str(camera_id).lower()
    if lowered in RIGHT_CAMERA_IDS or "right" in lowered:
        return "right"
    if lowered == "left" or "left" in lowered:
        return "left"
    return lowered


def limit_candidates(rays: Iterable[RayObservation], max_candidates_per_frame: int) -> List[RayObservation]:
    grouped: Dict[Tuple[str, int], List[RayObservation]] = {}
    for ray in rays:
        grouped.setdefault((ray.camera_id, ray.frame_index), []).append(ray)
    limited: List[RayObservation] = []
    for candidates in grouped.values():
        limited.extend(sorted(candidates, key=lambda item: item.confidence, reverse=True)[:max_candidates_per_frame])
    return sorted(limited, key=lambda ray: (ray.t_ns, ray.camera_id, ray.frame_index))


def ray_counts(rays: Iterable[RayObservation]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for ray in rays:
        counts[ray.camera_id] = counts.get(ray.camera_id, 0) + 1
    return counts


def seed_from_request_or_rays(
    request: TrajectoryFitRequest,
    rays: List[RayObservation],
    camera_models: Dict[str, RayCameraModel],
    t0_ns: int,
) -> Optional[np.ndarray]:
    if len(request.observations) >= 2:
        obs_sorted = sorted(request.observations, key=lambda obs: obs.t_ns)
        times_s = np.array([(obs.t_ns - obs_sorted[0].t_ns) / 1e9 for obs in obs_sorted], dtype=float)
        positions = np.array([[obs.X, obs.Y, obs.Z] for obs in obs_sorted], dtype=float)
        return _seed_state(times_s, positions)

    paired = paired_triangulations(rays, camera_models, request.max_time_offset_ms)
    if len(paired) < 2:
        return None
    paired = sorted(paired, key=lambda item: item[0])
    times_s = np.array([(time_ns - t0_ns) / 1e9 for time_ns, _ in paired], dtype=float)
    positions = np.array([position for _, position in paired], dtype=float)
    return _seed_state(times_s, positions)


def paired_triangulations(
    rays: List[RayObservation],
    camera_models: Dict[str, RayCameraModel],
    max_time_offset_ms: float,
) -> List[Tuple[int, np.ndarray]]:
    left = [ray for ray in rays if ray.camera_id == "left"]
    right = [ray for ray in rays if ray.camera_id == "right"]
    if not left or not right:
        return []
    max_delta_ns = int(max_time_offset_ms * 1e6)
    paired: List[Tuple[int, np.ndarray]] = []
    for left_ray in left:
        candidates = [
            right_ray
            for right_ray in right
            if abs(right_ray.t_ns - left_ray.t_ns) <= max_delta_ns
        ]
        if not candidates:
            continue
        right_ray = min(candidates, key=lambda ray: abs(ray.t_ns - left_ray.t_ns))
        point = triangulate_ray_pair(left_ray, right_ray, camera_models)
        if point is not None and np.all(np.isfinite(point)):
            paired.append(((left_ray.t_ns + right_ray.t_ns) // 2, point))
    return paired


def triangulate_ray_pair(
    left_ray: RayObservation,
    right_ray: RayObservation,
    camera_models: Dict[str, RayCameraModel],
) -> Optional[np.ndarray]:
    left_origin, left_dir = camera_models["left"].pixel_to_world_ray((left_ray.u, left_ray.v))
    right_origin, right_dir = camera_models["right"].pixel_to_world_ray((right_ray.u, right_ray.v))
    a = np.stack([left_dir, -right_dir], axis=1)
    b = right_origin - left_origin
    try:
        params, *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    p_left = left_origin + params[0] * left_dir
    p_right = right_origin + params[1] * right_dir
    return (p_left + p_right) * 0.5


def pixel_residual_vector(
    params: np.ndarray,
    request: TrajectoryFitRequest,
    rays: List[RayObservation],
    camera_models: Dict[str, RayCameraModel],
    t0_ns: int,
) -> np.ndarray:
    residuals: List[float] = []
    for ray in rays:
        t_s = ray_time_s(ray, params[7], t0_ns)
        predicted = propagate_ray(params[:6], t_s, request.wind_ft_s)
        uv_pred = camera_models[ray.camera_id].project(predicted[:3])
        weight = max(float(ray.confidence), 0.05) ** 0.5
        residuals.extend(((uv_pred - np.array([ray.u, ray.v], dtype=float)) * weight).tolist())
    residuals.append((float(params[6]) - request.drag_k0) / max(request.drag_sigma, 1e-6))
    sigma_dt_s = max(request.time_offset_sigma_ms / 1000.0, request.max_time_offset_ms / 2000.0, 1e-6)
    residuals.append((float(params[7]) - request.time_offset_prior_ms / 1000.0) / sigma_dt_s)
    if request.radar_speed_mph is not None:
        predicted_speed = speed_mph(params[:6])
        residuals.append((predicted_speed - float(request.radar_speed_mph)) / 2.0)
    return np.asarray(residuals, dtype=float)


def ray_time_s(ray: RayObservation, right_offset_s: float, t0_ns: int) -> float:
    time_s = (ray.t_ns - t0_ns) / 1e9
    if ray.camera_id == "right":
        time_s += right_offset_s
    return time_s


def build_samples(
    params: np.ndarray,
    rays: List[RayObservation],
    t0_ns: int,
    wind: Optional[Tuple[float, float, float]],
    plate_z_ft: float,
) -> List[TrackSample]:
    if not rays:
        return []
    times = sorted({max((ray.t_ns - t0_ns) / 1e9, 0.0) for ray in rays})
    if len(times) >= 2:
        plate_t = linear_plate_time_s(params, plate_z_ft)
        if plate_t is not None and times[-1] < plate_t <= times[-1] + 0.75:
            times.append(float(plate_t))
        dense_count = max(len(times), 80)
        dense_times = np.linspace(times[0], times[-1], dense_count)
    else:
        dense_times = np.asarray(times, dtype=float)
    samples: List[TrackSample] = []
    for t_s in dense_times:
        predicted = propagate_ray(params[:6], float(t_s), wind)
        samples.append(
            TrackSample(
                t_ns=int(t0_ns + float(t_s) * 1e9),
                X=float(predicted[0]),
                Y=float(predicted[1]),
                Z=float(predicted[2]),
                Vx=float(predicted[3]),
                Vy=float(predicted[4]),
                Vz=float(predicted[5]),
            )
        )
    return samples


def linear_plate_time_s(params: np.ndarray, plate_z_ft: float) -> Optional[float]:
    z0 = float(params[2])
    vz = float(params[5])
    if abs(vz) < 1e-9:
        return None
    t_s = (float(plate_z_ft) - z0) / vz
    if t_s < 0.0:
        return None
    return t_s


def build_ray_residual_reports(
    params: np.ndarray,
    request: TrajectoryFitRequest,
    rays: List[RayObservation],
    camera_models: Dict[str, RayCameraModel],
    t0_ns: int,
) -> List[ResidualReport]:
    reports: List[ResidualReport] = []
    for ray in rays:
        t_s = ray_time_s(ray, params[7], t0_ns)
        predicted = propagate_ray(params[:6], t_s, request.wind_ft_s)
        uv_pred = camera_models[ray.camera_id].project(predicted[:3])
        residual_px = float(np.linalg.norm(uv_pred - np.array([ray.u, ray.v], dtype=float)))
        reports.append(
            ResidualReport(
                t_ns=ray.t_ns,
                residual_px=residual_px,
                normalized_residual=residual_px / max(request.max_reprojection_px, 1e-6),
                inlier=residual_px <= request.max_reprojection_px,
            )
        )
    return reports


def select_graph_inliers(
    request: TrajectoryFitRequest,
    rays: List[RayObservation],
    camera_models: Dict[str, RayCameraModel],
) -> List[RayObservation]:
    if not rays:
        return []
    paired = paired_triangulations(rays, camera_models, request.max_time_offset_ms)
    if len(paired) < 2:
        return []

    t0_ns = min(ray.t_ns for ray in rays)
    seeds = candidate_seed_states(paired, t0_ns)
    if not seeds:
        return []

    best_score = -float("inf")
    best_inliers: List[RayObservation] = []
    threshold_px = max(request.max_reprojection_px * 16.0, 50.0)
    for seed in seeds:
        params = np.array(
            [seed[0], seed[1], seed[2], seed[3], seed[4], seed[5], request.drag_k0, request.time_offset_prior_ms / 1000.0],
            dtype=float,
        )
        inliers: List[RayObservation] = []
        residual_sum = 0.0
        for ray in rays:
            residual_px = single_ray_residual_px(params, request, ray, camera_models, t0_ns)
            if residual_px <= threshold_px:
                inliers.append(ray)
                residual_sum += residual_px
        if not inliers:
            continue
        counts = ray_counts(inliers)
        if counts.get("left", 0) < request.min_rays_per_camera or counts.get("right", 0) < request.min_rays_per_camera:
            continue
        score = sum(ray.confidence for ray in inliers) - 0.01 * residual_sum
        if score > best_score:
            best_score = score
            best_inliers = inliers
    return best_inliers


def candidate_seed_states(paired: List[Tuple[int, np.ndarray]], t0_ns: int) -> List[np.ndarray]:
    paired = sorted(paired, key=lambda item: item[0])
    seeds: List[np.ndarray] = []
    if len(paired) >= 2:
        times_s = np.array([(time_ns - t0_ns) / 1e9 for time_ns, _ in paired], dtype=float)
        positions = np.array([position for _, position in paired], dtype=float)
        seeds.append(_seed_state(times_s, positions))

    max_pairs = min(len(paired), 12)
    for i in range(max_pairs):
        for j in range(i + 1, max_pairs):
            dt = (paired[j][0] - paired[i][0]) / 1e9
            if abs(dt) < 0.03:
                continue
            times_s = np.array([(paired[i][0] - t0_ns) / 1e9, (paired[j][0] - t0_ns) / 1e9], dtype=float)
            positions = np.array([paired[i][1], paired[j][1]], dtype=float)
            seeds.append(_seed_state(times_s, positions))
    return seeds


def single_ray_residual_px(
    params: np.ndarray,
    request: TrajectoryFitRequest,
    ray: RayObservation,
    camera_models: Dict[str, RayCameraModel],
    t0_ns: int,
) -> float:
    t_s = ray_time_s(ray, params[7], t0_ns)
    predicted = propagate_ray(params[:6], t_s, request.wind_ft_s)
    uv_pred = camera_models[ray.camera_id].project(predicted[:3])
    return float(np.linalg.norm(uv_pred - np.array([ray.u, ray.v], dtype=float)))


def inlier_ratio(residuals: List[ResidualReport]) -> Optional[float]:
    if not residuals:
        return None
    return sum(1 for residual in residuals if residual.inlier) / len(residuals)


def propagate_ray(
    state: np.ndarray,
    t_s: float,
    wind: Optional[Tuple[float, float, float]],
) -> np.ndarray:
    dt = max(float(t_s), 0.0)
    wind_vec = np.asarray(wind, dtype=float) if wind is not None else np.zeros(3, dtype=float)
    velocity0 = state[3:6] - wind_vec
    position = state[:3] + velocity0 * dt + np.array([0.0, 0.5 * GRAVITY_FT_S2 * dt * dt, 0.0])
    velocity = velocity0 + np.array([0.0, GRAVITY_FT_S2 * dt, 0.0]) + wind_vec
    return np.concatenate([position, velocity])


def expected_plate_error_from_px(
    rmse_px: Optional[float],
    plate_crossing: Optional[Tuple[Tuple[float, float, float], int]],
) -> Optional[float]:
    if plate_crossing is None or rmse_px is None:
        return None
    return max(0.02, float(rmse_px) / 80.0)


def radar_residual_mph(params: np.ndarray, request: TrajectoryFitRequest) -> Optional[float]:
    if request.radar_speed_mph is None:
        return None
    return speed_mph(params[:6]) - float(request.radar_speed_mph)


def speed_mph(state: np.ndarray) -> float:
    velocity = state[3:6]
    return float(np.linalg.norm(velocity) * 0.681818)


def failure_result(model_name: str, diagnostics: TrajectoryDiagnostics) -> TrajectoryFitResult:
    return TrajectoryFitResult(
        model_name=model_name,
        samples=[],
        plate_crossing_xyz_ft=None,
        plate_crossing_t_ns=None,
        expected_plate_error_ft=None,
        confidence=0.0,
        diagnostics=diagnostics,
    )


def least_squares_multistart(
    params0: np.ndarray,
    request: TrajectoryFitRequest,
    rays: List[RayObservation],
    camera_models: Dict[str, RayCameraModel],
    t0_ns: int,
    bounds: Tuple[np.ndarray, np.ndarray],
    loss: str,
    least_squares_fn,
):
    """Run least-squares optimization from multiple starting points."""
    starts = [request.time_offset_prior_ms / 1000.0, 0.0]
    max_offset_s = request.max_time_offset_ms / 1000.0
    for fraction in (0.5, 1.0):
        starts.extend([max_offset_s * fraction, -max_offset_s * fraction])

    best = None
    for dt_start in starts:
        trial = params0.copy()
        trial[7] = float(np.clip(dt_start, bounds[0][7] + 1e-6, bounds[1][7] - 1e-6))
        result = least_squares_fn(
            lambda params: pixel_residual_vector(params, request, rays, camera_models, t0_ns),
            trial,
            bounds=bounds,
            max_nfev=request.max_iter,
            loss=loss,
            f_scale=max(request.max_reprojection_px, 1.0),
        )
        if best is None or result.cost < best.cost:
            best = result
    return best
