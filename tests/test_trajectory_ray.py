from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.services.rig_profile import RigProfileService
from app.services.rig_profile_models import RigProfile
from calib.field_transform import FieldTransform
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


def test_camera_model_epipolar_distance_uses_fundamental_matrix() -> None:
    fundamental = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, -1.0],
            [0.0, 1.0, 0.0],
        ]
    )
    camera = CameraModel(
        fx=1000.0,
        fy=1000.0,
        cx=0.0,
        cy=0.0,
        R=np.eye(3),
        t=np.zeros(3),
        fundamental_matrix=fundamental,
    )
    assert camera.epipolar_distance(np.array([10.0, 20.0]), np.array([8.0, 20.0])) == 0.0


def test_camera_model_world_frame_transform_preserves_projection_and_rotates_rays() -> None:
    camera = _camera_models()["right"]
    matrix = np.array(
        [[0.0, -1.0, 0.0, 2.0], [1.0, 0.0, 0.0, 3.0], [0.0, 0.0, 1.0, 4.0], [0.0, 0.0, 0.0, 1.0]],
        dtype=float,
    )
    point_camera_world = np.array([0.25, -0.5, 50.0])
    point_field = (matrix @ np.append(point_camera_world, 1.0))[:3]

    transformed = camera.in_transformed_world_frame(matrix)

    assert transformed.project(point_field) == pytest.approx(camera.project(point_camera_world))
    expected_center = (matrix @ np.append(camera.camera_center_world(), 1.0))[:3]
    assert transformed.camera_center_world() == pytest.approx(expected_center)
    old_center, old_direction = camera.pixel_to_world_ray((camera.cx, camera.cy))
    new_center, new_direction = transformed.pixel_to_world_ray((camera.cx, camera.cy))
    assert new_center == pytest.approx((matrix @ np.append(old_center, 1.0))[:3])
    assert new_direction == pytest.approx(matrix[:3, :3] @ old_direction)


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


def test_analyzer_loads_ray_extrinsics_in_validated_field_frame(tmp_path, monkeypatch) -> None:
    fx = 1200.0
    cx = 960.0
    cy = 540.0
    k = np.array([[fx, 0.0, cx], [0.0, fx, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
    calibration_path = tmp_path / "stereo_calibration.npz"
    np.savez(
        calibration_path,
        mtx_left=k,
        mtx_right=k,
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[-304.8], [0.0], [0.0]], dtype=np.float64),
    )
    transform = FieldTransform(
        ((0, -1, 0, 2), (1, 0, 0, 3), (0, 0, 1, 4), (0, 0, 0, 1)),
        0.01,
        "plate-fixture",
    )
    profile = RigProfile.from_dict(
        {
            "profile_id": "rig",
            "backend": "sim",
            "calibration_file": str(calibration_path),
            "field_transform": transform.to_payload(),
        }
    )
    monkeypatch.setattr(RigProfileService, "load_active", lambda self: profile)
    monkeypatch.setattr(RigProfileService, "calibration_path", lambda self, loaded: calibration_path)
    config = load_config(Path("configs/default.yaml"))
    analyzer = PitchAnalyzer(config, get_ball_radius_fn=lambda: 1.45, radar_speed_fn=lambda: None)

    models = analyzer._load_ray_camera_models()

    camera_point = np.array([0.0, 0.0, 50.0])
    field_point = np.asarray(transform.matrix_4x4) @ np.append(camera_point, 1.0)
    assert models["left"].camera_center_world() == pytest.approx(np.array([2.0, 3.0, 4.0]))
    assert models["left"].project(field_point[:3]) == pytest.approx(np.array([cx, cy]))


def test_analyzer_fails_closed_when_ray_field_transform_is_unproven(monkeypatch) -> None:
    profile = RigProfile.from_dict(
        {
            "profile_id": "rig-without-field-frame",
            "backend": "sim",
            "field_transform": {},
        }
    )
    monkeypatch.setattr(RigProfileService, "load_active", lambda self: profile)
    config = load_config(Path("configs/default.yaml"))
    analyzer = PitchAnalyzer(config, get_ball_radius_fn=lambda: 1.45, radar_speed_fn=lambda: None)

    assert analyzer._load_ray_camera_models() == {}


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
    observations = [
        replace(
            obs,
            covariance=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, (1.0 + index * 0.1) ** 2)),
        )
        for index, obs in enumerate(simulate_ballistic(SimConfig(dt_s=0.02, outlier_prob=0.0, noise_ft=0.0)))
    ]

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
    assert summary.observation_mean_depth_sigma_ft is not None
    assert 2.4 < summary.observation_mean_depth_sigma_ft < 2.5
    assert summary.observation_max_depth_sigma_ft is not None
    assert 3.9 < summary.observation_max_depth_sigma_ft < 4.0
    assert summary.observation_quality_status == "PASS"
    assert summary.observation_rejection_reasons == []
    assert summary.observation_warning_reasons == []
    failure_codes = summary.trajectory_comparison["ray_reprojection"]["diagnostics"]["failure_codes"]
    assert failure_codes
    assert failure_codes[0] in {"CAMERA_MODEL_MISSING", "INSUFFICIENT_RAYS"}
