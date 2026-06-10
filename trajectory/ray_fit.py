"""Multi-view ray/reprojection trajectory fitters."""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional

import numpy as np

from contracts import RayObservation
from trajectory.base import TrajectoryFitterBase
from trajectory.confidence import ConfidenceScorer
from trajectory.contracts import (
    FailureCode,
    TrajectoryDiagnostics,
    TrajectoryFitRequest,
    TrajectoryFitResult,
)
from trajectory.physics import _condition_number, _find_plate_crossing, _is_monotonic_z, _rmse
from trajectory.ray_fit_helpers import (
    RIGHT_CAMERA_IDS,
    GRAVITY_FT_S2,
    build_ray_residual_reports,
    build_samples,
    expected_plate_error_from_px,
    failure_result,
    inlier_ratio,
    least_squares_multistart,
    limit_candidates,
    normalize_camera_models,
    radar_residual_mph,
    ray_counts,
    rays_with_known_cameras,
    seed_from_request_or_rays,
    select_graph_inliers,
)

try:
    from scipy.optimize import least_squares
except Exception:  # pragma: no cover - handled at runtime
    least_squares = None


class RayReprojectionFitter(TrajectoryFitterBase):
    """Fit a single 3D trajectory directly against per-camera pixel rays."""

    def __init__(self) -> None:
        super().__init__()
        self._scorer = ConfidenceScorer()

    def maybe_fit(self) -> Optional[TrajectoryFitResult]:
        return None

    def finalize_fit(self) -> TrajectoryFitResult:
        if self._request is None:
            raise RuntimeError("No request set.")
        return self.fit_trajectory(self._request)

    def fit_trajectory(self, request: TrajectoryFitRequest) -> TrajectoryFitResult:
        return self._fit(
            request,
            limit_candidates(request.ray_observations, request.max_candidates_per_frame),
            model_name="ray_reprojection",
        )

    def _fit(
        self,
        request: TrajectoryFitRequest,
        rays: List[RayObservation],
        model_name: str,
    ) -> TrajectoryFitResult:
        diagnostics = TrajectoryDiagnostics()
        camera_models = normalize_camera_models(request.camera_models)
        if len(camera_models) < 2:
            diagnostics.failure_codes.append(FailureCode.CAMERA_MODEL_MISSING)
            return failure_result(model_name, diagnostics)
        if least_squares is None:
            diagnostics.failure_codes.append(FailureCode.OPT_DID_NOT_CONVERGE)
            diagnostics.notes.append("scipy unavailable")
            return failure_result(model_name, diagnostics)

        normalized_rays = rays_with_known_cameras(rays, camera_models)
        counts = ray_counts(normalized_rays)
        if any(counts.get(camera_id, 0) < request.min_rays_per_camera for camera_id in ("left", "right")):
            diagnostics.failure_codes.append(FailureCode.INSUFFICIENT_RAYS)
            diagnostics.notes.append(f"ray counts: {counts}")
            return failure_result(model_name, diagnostics)

        t0_ns = min(ray.t_ns for ray in normalized_rays)
        seed = seed_from_request_or_rays(request, normalized_rays, camera_models, t0_ns)
        if seed is None:
            diagnostics.failure_codes.append(FailureCode.REPROJECTION_FAILED)
            diagnostics.notes.append("could not build ray seed")
            return failure_result(model_name, diagnostics)

        bounds = (
            np.array([-100.0, -100.0, -50.0, -300.0, -300.0, -400.0, 0.0, -request.max_time_offset_ms / 1000.0]),
            np.array([100.0, 150.0, 200.0, 300.0, 300.0, 400.0, 0.3, request.max_time_offset_ms / 1000.0]),
        )
        params0 = np.clip(
            np.array(
                [seed[0], seed[1], seed[2], seed[3], seed[4], seed[5], request.drag_k0, request.time_offset_prior_ms / 1000.0],
                dtype=float,
            ),
            bounds[0] + 1e-6,
            bounds[1] - 1e-6,
        )
        loss = request.robust_loss if request.robust_loss in {"linear", "soft_l1", "huber", "cauchy", "arctan"} else "huber"
        result = least_squares_multistart(
            params0=params0,
            request=request,
            rays=normalized_rays,
            camera_models=camera_models,
            t0_ns=t0_ns,
            bounds=bounds,
            loss=loss,
            least_squares_fn=least_squares,
        )

        failure_codes = list(diagnostics.failure_codes)
        if not result.success:
            failure_codes.append(FailureCode.OPT_DID_NOT_CONVERGE)

        params = result.x
        samples = build_samples(params, normalized_rays, t0_ns, request.wind_ft_s, request.plate_plane_z_ft)
        plate_crossing = _find_plate_crossing(samples, request.plate_plane_z_ft)
        if plate_crossing is None:
            failure_codes.append(FailureCode.NO_PLATE_CROSSING)
        if not _is_monotonic_z(samples):
            failure_codes.append(FailureCode.NON_MONOTONIC_Z)

        residuals = build_ray_residual_reports(params, request, normalized_rays, camera_models, t0_ns)
        rmse_px = _rmse([res.residual_px for res in residuals if res.residual_px is not None])
        diagnostics = TrajectoryDiagnostics(
            rmse_px=rmse_px,
            inlier_ratio=inlier_ratio(residuals),
            condition_number=_condition_number(result.jac),
            drag_param=float(params[6]),
            drag_param_ok=bool(params[6] >= 0.0),
            radar_residual_mph=radar_residual_mph(params, request),
            estimated_camera_time_offset_ms=float(params[7] * 1000.0),
            failure_codes=failure_codes,
            notes=list(diagnostics.notes),
        )
        expected_error = expected_plate_error_from_px(rmse_px, plate_crossing)
        return TrajectoryFitResult(
            model_name=model_name,
            samples=samples,
            plate_crossing_xyz_ft=plate_crossing[0] if plate_crossing else None,
            plate_crossing_t_ns=plate_crossing[1] if plate_crossing else None,
            expected_plate_error_ft=expected_error,
            confidence=self._scorer.confidence_from_error(expected_error),
            diagnostics=diagnostics,
            residuals=residuals,
        )


class RayGraphFitter(RayReprojectionFitter):
    """Robust ray fitter that selects inlier rays before final reprojection fit."""

    def fit_trajectory(self, request: TrajectoryFitRequest) -> TrajectoryFitResult:
        rays = limit_candidates(request.ray_observations, request.max_candidates_per_frame)
        camera_models = normalize_camera_models(request.camera_models)
        if len(camera_models) < 2:
            return failure_result(
                "ray_graph",
                TrajectoryDiagnostics(failure_codes=[FailureCode.CAMERA_MODEL_MISSING]),
            )

        normalized_rays = rays_with_known_cameras(rays, camera_models)
        inlier_rays = select_graph_inliers(request, normalized_rays, camera_models)
        if len(inlier_rays) < max(2 * request.min_rays_per_camera, 4):
            return failure_result(
                "ray_graph",
                TrajectoryDiagnostics(
                    failure_codes=[FailureCode.INSUFFICIENT_RAYS],
                    notes=["ray graph could not find enough inliers"],
                ),
            )

        result = self._fit(request, inlier_rays, model_name="ray_graph")
        notes = list(result.diagnostics.notes)
        notes.append(f"graph_inliers={len(inlier_rays)}/{len(normalized_rays)}")
        return replace(result, diagnostics=replace(result.diagnostics, notes=notes))
