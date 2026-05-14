from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from configs.settings import TrajectoryConfig, load_config
from contracts import RayObservation
from trajectory.camera_model import CameraModel, load_stereo_ray_camera_models
from trajectory.contracts import TrajectoryFitRequest
from trajectory.ray_fit import RayGraphFitter, RayReprojectionFitter
from trajectory.sim import SimConfig, simulate_ballistic


def _camera_models() -> dict[str, CameraModel]:
    fx = 1200.0
    cx = 960.0
    cy = 540.0
    baseline_ft = 1.5
    return {
        "left": CameraModel(
            fx=fx,
            fy=fx,
            cx=cx,
            cy=cy,
            R=np.eye(3),
            t=np.zeros(3),
            camera_id="left",
        ),
        "right": CameraModel(
            fx=fx,
            fy=fx,
            cx=cx,
            cy=cy,
            R=np.eye(3),
            t=np.array([-baseline_ft, 0.0, 0.0]),
            camera_id="right",
        ),
    }


def _trajectory_position(t_s: float) -> np.ndarray:
    return np.array(
        [
            0.2 + 0.5 * t_s,
            5.5 + 1.0 * t_s + 0.5 * -32.174 * t_s * t_s,
            55.0 - 90.0 * t_s,
        ],
        dtype=float,
    )


def _synthetic_rays(
    offset_s: float = 0.010,
    noise_px: float = 0.0,
    clutter: bool = False,
) -> list[RayObservation]:
    rng = np.random.default_rng(3)
    models = _camera_models()
    rays: list[RayObservation] = []
    for frame_index, t_s in enumerate(np.arange(0.0, 0.55, 1 / 60)):
        for camera_id, camera_dt in (("left", 0.0), ("right", offset_s)):
            uv = models[camera_id].project(_trajectory_position(t_s + camera_dt))
            uv = uv + rng.normal(0.0, noise_px, size=2)
            rays.append(
                RayObservation(
                    camera_id=camera_id,
                    frame_index=frame_index,
                    t_ns=int(t_s * 1e9),
                    u=float(uv[0]),
                    v=float(uv[1]),
                    radius_px=5.0,
                    confidence=1.0,
                )
            )
            if clutter and frame_index % 3 != 0:
                false_uv = uv + rng.normal([120.0, -90.0], [20.0, 20.0])
                rays.append(
                    RayObservation(
                        camera_id=camera_id,
                        frame_index=frame_index,
                        t_ns=int(t_s * 1e9),
                        u=float(false_uv[0]),
                        v=float(false_uv[1]),
                        radius_px=5.0,
                        confidence=0.8,
                    )
                )
    return rays


def _request(rays: list[RayObservation], max_reprojection_px: float = 3.0) -> TrajectoryFitRequest:
    return TrajectoryFitRequest(
        observations=[],
        plate_plane_z_ft=0.0,
        ray_observations=rays,
        camera_models=_camera_models(),
        max_time_offset_ms=20.0,
        min_rays_per_camera=4,
        max_candidates_per_frame=2,
        max_reprojection_px=max_reprojection_px,
        drag_k0=0.0,
        drag_sigma=0.01,
        max_iter=80,
    )


def test_ray_reprojection_estimates_unsynced_camera_offset() -> None:
    result = RayReprojectionFitter().fit_trajectory(_request(_synthetic_rays(offset_s=0.010)))

    assert result.plate_crossing_xyz_ft is not None
    assert result.diagnostics.rmse_px is not None
    assert result.diagnostics.rmse_px < 0.1
    assert result.diagnostics.estimated_camera_time_offset_ms is not None
    assert abs(result.diagnostics.estimated_camera_time_offset_ms - 10.0) < 1.0
    assert abs(result.plate_crossing_xyz_ft[2]) < 1e-6


def test_load_stereo_ray_camera_models_uses_feet(tmp_path) -> None:
    fx = 1200.0
    cx = 960.0
    cy = 540.0
    k = np.array([[fx, 0.0, cx], [0.0, fx, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
    calibration_path = tmp_path / "stereo_calibration.npz"
    np.savez(
        calibration_path,
        img_size=np.array([1920, 1080]),
        mtx_left=k,
        mtx_right=k,
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[-304.8], [0.0], [0.0]], dtype=np.float64),
    )

    models = load_stereo_ray_camera_models(calibration_path)
    point = np.array([0.0, 0.0, 50.0], dtype=float)

    assert set(models) == {"left", "right"}
    assert np.allclose(models["right"].t, np.array([-1.0, 0.0, 0.0]))
    assert np.allclose(models["left"].project(point), np.array([cx, cy]))
    assert np.allclose(models["right"].project(point), np.array([cx - fx / 50.0, cy]))


def test_ray_graph_rejects_clutter_better_than_direct_fit() -> None:
    request = _request(_synthetic_rays(offset_s=0.010, noise_px=0.2, clutter=True), max_reprojection_px=4.0)

    direct = RayReprojectionFitter().fit_trajectory(request)
    graph = RayGraphFitter().fit_trajectory(request)

    assert graph.plate_crossing_xyz_ft is not None
    assert graph.diagnostics.rmse_px is not None
    assert direct.diagnostics.rmse_px is not None
    assert graph.diagnostics.rmse_px < direct.diagnostics.rmse_px * 0.25
    assert abs((graph.diagnostics.estimated_camera_time_offset_ms or 0.0) - 10.0) < 1.0


def test_analyzer_falls_back_to_stereo_when_ray_calibration_missing() -> None:
    config = load_config(Path("configs/default.yaml"))
    config = replace(
        config,
        trajectory=TrajectoryConfig(
            primary_mode="ray_reprojection",
            compare_modes=(),
            fallback_to_stereo=True,
            ray=config.trajectory.ray,
        ),
    )
    analyzer = PitchAnalyzer(config, get_ball_radius_fn=lambda: 1.45, radar_speed_fn=lambda: None)
    observations = simulate_ballistic(SimConfig(dt_s=0.02, outlier_prob=0.0, noise_ft=0.0))

    summary = analyzer.analyze_pitch(
        pitch_id="pitch-ray-fallback",
        start_ns=observations[0].t_ns,
        end_ns=observations[-1].t_ns,
        observations=observations,
        ray_observations=[],
    )

    assert summary.trajectory_mode == "stereo_3d"
    assert summary.trajectory_plate_z_ft is not None
    assert summary.trajectory_comparison is not None
    assert summary.trajectory_comparison["ray_reprojection"]["diagnostics"]["failure_codes"] == [
        "CAMERA_MODEL_MISSING"
    ]
