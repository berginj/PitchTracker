"""Reusable synthetic stereo geometry fixtures for calibration/error-budget tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from contracts import Detection, StereoObservation
from stereo.calibrated_stereo import CalibratedStereoGeometry, CalibratedStereoMatcher
from stereo.association import StereoMatch


MM_PER_FOOT = 304.8


@dataclass(frozen=True)
class ProjectedStereoPoint:
    xyz_ft: np.ndarray
    left_uv: np.ndarray
    right_uv: np.ndarray


def make_rectified_geometry(
    *,
    baseline_ft: float = 1.625,
    focal_px: float = 1200.0,
    cx: float = 640.0,
    cy: float = 360.0,
    epipolar_epsilon_px: float = 2.0,
    z_min_ft: float = 3.0,
    z_max_ft: float = 90.0,
) -> CalibratedStereoGeometry:
    baseline_mm = baseline_ft * MM_PER_FOOT
    k = np.array([[focal_px, 0.0, cx], [0.0, focal_px, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
    rmat = np.eye(3, dtype=np.float64)
    tvec = np.array([[-baseline_mm], [0.0], [0.0]], dtype=np.float64)
    return CalibratedStereoGeometry(
        mtx_left=k,
        dist_left=np.zeros(5, dtype=np.float64),
        mtx_right=k,
        dist_right=np.zeros(5, dtype=np.float64),
        R=rmat,
        T=tvec,
        F=_fundamental_from_rt(k, k, rmat, tvec),
        img_size=(1280, 720),
        epipolar_epsilon_px=epipolar_epsilon_px,
        z_min_ft=z_min_ft,
        z_max_ft=z_max_ft,
    )


def make_misaligned_geometry(
    *,
    baseline_ft: float = 1.625,
    focal_px: float = 1200.0,
    cx: float = 640.0,
    cy: float = 360.0,
    yaw_deg: float = 1.5,
    pitch_deg: float = -0.7,
    roll_deg: float = 1.2,
    vertical_offset_ft: float = 0.08,
    forward_offset_ft: float = 0.04,
    epipolar_epsilon_px: float = 2.0,
    z_min_ft: float = 3.0,
    z_max_ft: float = 90.0,
    time_sync_offset_ns: int = 0,
) -> CalibratedStereoGeometry:
    baseline_mm = baseline_ft * MM_PER_FOOT
    k = np.array([[focal_px, 0.0, cx], [0.0, focal_px, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
    rmat = _rotation_matrix(yaw_deg=yaw_deg, pitch_deg=pitch_deg, roll_deg=roll_deg)
    tvec = np.array(
        [[-baseline_mm], [vertical_offset_ft * MM_PER_FOOT], [forward_offset_ft * MM_PER_FOOT]],
        dtype=np.float64,
    )
    return CalibratedStereoGeometry(
        mtx_left=k,
        dist_left=np.zeros(5, dtype=np.float64),
        mtx_right=k,
        dist_right=np.zeros(5, dtype=np.float64),
        R=rmat,
        T=tvec,
        F=_fundamental_from_rt(k, k, rmat, tvec),
        img_size=(1280, 720),
        epipolar_epsilon_px=epipolar_epsilon_px,
        z_min_ft=z_min_ft,
        z_max_ft=z_max_ft,
        time_sync_offset_ns=time_sync_offset_ns,
    )


def project_points(
    geometry: CalibratedStereoGeometry,
    points_ft: Iterable[tuple[float, float, float]],
) -> list[ProjectedStereoPoint]:
    return [
        ProjectedStereoPoint(
            xyz_ft=np.asarray(point_ft, dtype=np.float64),
            left_uv=_project(geometry.mtx_left, np.eye(3), np.zeros((3, 1)), point_ft),
            right_uv=_project(geometry.mtx_right, geometry.R, geometry.T, point_ft),
        )
        for point_ft in points_ft
    ]


def triangulate_projected_point(
    matcher: CalibratedStereoMatcher,
    projected: ProjectedStereoPoint,
    *,
    left_noise_px: tuple[float, float] = (0.0, 0.0),
    right_noise_px: tuple[float, float] = (0.0, 0.0),
    frame_index: int = 0,
    left_t_ns: int | None = None,
    right_t_ns: int | None = None,
) -> tuple[StereoMatch, StereoObservation]:
    left_uv = projected.left_uv + np.asarray(left_noise_px, dtype=np.float64)
    right_uv = projected.right_uv + np.asarray(right_noise_px, dtype=np.float64)
    left = _detection("left", left_uv, frame_index, left_t_ns)
    right = _detection("right", right_uv, frame_index, right_t_ns)
    match = matcher.match(left, right)
    if match is None:
        raise AssertionError(f"Synthetic stereo match rejected: left={left_uv}, right={right_uv}")
    return match, matcher.triangulate(match)


def _project(k: np.ndarray, rmat: np.ndarray, tvec_mm: np.ndarray, point_ft: tuple[float, float, float]) -> np.ndarray:
    point_mm = np.asarray(point_ft, dtype=np.float64).reshape(3, 1) * MM_PER_FOOT
    camera_point = rmat @ point_mm + tvec_mm.reshape(3, 1)
    x, y, z = camera_point.reshape(3)
    return np.array([k[0, 0] * x / z + k[0, 2], k[1, 1] * y / z + k[1, 2]], dtype=np.float64)


def _detection(camera_id: str, uv: np.ndarray, frame_index: int, t_ns: int | None = None) -> Detection:
    return Detection(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=frame_index * 8_333_333 if t_ns is None else t_ns,
        u=float(uv[0]),
        v=float(uv[1]),
        radius_px=4.0,
        confidence=1.0,
    )


def _rotation_matrix(*, yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    yaw = np.deg2rad(yaw_deg)
    pitch = np.deg2rad(pitch_deg)
    roll = np.deg2rad(roll_deg)
    ry = np.array(
        [[np.cos(yaw), 0.0, np.sin(yaw)], [0.0, 1.0, 0.0], [-np.sin(yaw), 0.0, np.cos(yaw)]],
        dtype=np.float64,
    )
    rx = np.array(
        [[1.0, 0.0, 0.0], [0.0, np.cos(pitch), -np.sin(pitch)], [0.0, np.sin(pitch), np.cos(pitch)]],
        dtype=np.float64,
    )
    rz = np.array(
        [[np.cos(roll), -np.sin(roll), 0.0], [np.sin(roll), np.cos(roll), 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    return rz @ ry @ rx


def _fundamental_from_rt(k_left: np.ndarray, k_right: np.ndarray, rmat: np.ndarray, tvec: np.ndarray) -> np.ndarray:
    tx = np.array(
        [
            [0.0, -tvec[2, 0], tvec[1, 0]],
            [tvec[2, 0], 0.0, -tvec[0, 0]],
            [-tvec[1, 0], tvec[0, 0], 0.0],
        ],
        dtype=np.float64,
    )
    return np.linalg.inv(k_right).T @ tx @ rmat @ np.linalg.inv(k_left)
