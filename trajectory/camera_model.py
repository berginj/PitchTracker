"""Camera model helpers for projection, rays, and saved stereo calibration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, cast

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - optional in headless/unit environments
    cv2 = None  # type: ignore[assignment]


MM_PER_FOOT = 304.8


@dataclass(frozen=True)
class CameraModel:
    fx: float
    fy: float
    cx: float
    cy: float
    R: np.ndarray
    t: np.ndarray
    distortion: Optional[Tuple[float, float, float, float, float]] = None
    fundamental_matrix: Optional[np.ndarray] = None
    camera_id: str = "camera"

    def project(self, xyz_ft: np.ndarray) -> np.ndarray:
        point = self.R @ xyz_ft.reshape(3, 1) + self.t.reshape(3, 1)
        x, y, z = point.flatten()
        if z == 0:
            z = 1e-6
        u = self.fx * (x / z) + self.cx
        v = self.fy * (y / z) + self.cy
        if self.distortion is None:
            return cast(np.ndarray, np.array([u, v], dtype=float))
        k1, k2, p1, p2, k3 = self.distortion
        xn = x / z
        yn = y / z
        r2 = xn * xn + yn * yn
        radial = 1 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2
        x_dist = xn * radial + 2 * p1 * xn * yn + p2 * (r2 + 2 * xn * xn)
        y_dist = yn * radial + p1 * (r2 + 2 * yn * yn) + 2 * p2 * xn * yn
        return cast(np.ndarray, np.array([self.fx * x_dist + self.cx, self.fy * y_dist + self.cy], dtype=float))

    def pixel_to_world_ray(self, uv: Tuple[float, float]) -> Tuple[np.ndarray, np.ndarray]:
        """Return camera center and unit ray direction in world feet."""
        x_norm, y_norm = self._undistort_to_normalized(uv)
        direction_camera = np.array([x_norm, y_norm, 1.0], dtype=float)
        direction_camera /= max(float(np.linalg.norm(direction_camera)), 1e-12)
        direction_world = self.R.T @ direction_camera
        direction_world /= max(float(np.linalg.norm(direction_world)), 1e-12)
        return self.camera_center_world(), direction_world

    def camera_center_world(self) -> np.ndarray:
        return cast(np.ndarray, (-self.R.T @ self.t.reshape(3, 1)).reshape(3))

    def in_transformed_world_frame(self, matrix_4x4: np.ndarray) -> "CameraModel":
        """Return equivalent extrinsics expressed in a new rigid world frame.

        ``matrix_4x4`` maps points from this model's current world frame into
        the new frame. Projection remains identical for corresponding points.
        """
        matrix = np.asarray(matrix_4x4, dtype=np.float64)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
            raise ValueError("world-frame transform must be a finite 4x4 matrix")
        if not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-6):
            raise ValueError("world-frame transform must be affine")
        rotation = matrix[:3, :3]
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5):
            raise ValueError("world-frame transform rotation must be orthonormal")
        if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-5):
            raise ValueError("world-frame transform rotation must have determinant +1")
        translation = matrix[:3, 3]
        new_rotation = self.R @ rotation.T
        new_translation = self.t.reshape(3) - new_rotation @ translation
        return CameraModel(
            fx=self.fx,
            fy=self.fy,
            cx=self.cx,
            cy=self.cy,
            R=new_rotation,
            t=new_translation,
            distortion=self.distortion,
            fundamental_matrix=self.fundamental_matrix,
            camera_id=self.camera_id,
        )

    def jacobian_project(self, xyz_ft: np.ndarray) -> np.ndarray:
        eps = 1e-4
        base = self.project(xyz_ft)
        jac: np.ndarray = np.zeros((2, 3), dtype=float)
        for i in range(3):
            delta: np.ndarray = np.zeros(3, dtype=float)
            delta[i] = eps
            perturbed = self.project(xyz_ft + delta)
            jac[:, i] = (perturbed - base) / eps
        return jac

    def epipolar_distance(self, left_uv: np.ndarray, right_uv: np.ndarray) -> Optional[float]:
        if self.fundamental_matrix is None:
            return None
        left = np.array([left_uv[0], left_uv[1], 1.0], dtype=float)
        line = self.fundamental_matrix @ left
        denom = (line[0] ** 2 + line[1] ** 2) ** 0.5
        if denom == 0:
            return None
        dist = abs(line[0] * right_uv[0] + line[1] * right_uv[1] + line[2]) / denom
        return float(dist)

    def _undistort_to_normalized(self, uv: Tuple[float, float]) -> Tuple[float, float]:
        if self.distortion is not None and cv2 is not None:
            camera_matrix = np.array(
                [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]],
                dtype=np.float64,
            )
            points = np.array([[[uv[0], uv[1]]]], dtype=np.float64)
            undistorted = cv2.undistortPoints(points, camera_matrix, np.asarray(self.distortion, dtype=np.float64))
            x_norm, y_norm = undistorted.reshape(2)
            return float(x_norm), float(y_norm)
        return (float((uv[0] - self.cx) / self.fx), float((uv[1] - self.cy) / self.fy))


RayCameraModel = CameraModel


def load_stereo_ray_camera_models(path: Path) -> Dict[str, RayCameraModel]:
    """Load left/right ray camera models from a full stereo calibration npz."""
    if not path.exists():
        raise FileNotFoundError(f"Calibration file not found: {path}")

    data = np.load(path, allow_pickle=True)
    required = {"mtx_left", "mtx_right", "dist_left", "dist_right", "R", "T"}
    missing = sorted(required.difference(data.files))
    if missing:
        raise KeyError(f"Calibration file missing required arrays: {', '.join(missing)}")

    mtx_left = np.asarray(data["mtx_left"], dtype=np.float64)
    mtx_right = np.asarray(data["mtx_right"], dtype=np.float64)

    # Basic validation
    if mtx_left.shape != (3, 3) or mtx_right.shape != (3, 3):
        raise ValueError("Calibration matrices must be 3x3")

    dist_left = _distortion_tuple(np.asarray(data["dist_left"], dtype=np.float64))
    dist_right = _distortion_tuple(np.asarray(data["dist_right"], dtype=np.float64))
    rmat = np.asarray(data["R"], dtype=np.float64)
    t_raw = np.asarray(data["T"], dtype=np.float64)
    if t_raw.size not in (3, 3):
        # reshape tolerant
        t_raw = t_raw.reshape(3)
    t_ft = t_raw.reshape(3) / MM_PER_FOOT
    fmat = np.asarray(data["F"], dtype=np.float64) if "F" in data else None

    left = RayCameraModel(
        fx=float(mtx_left[0, 0]),
        fy=float(mtx_left[1, 1]),
        cx=float(mtx_left[0, 2]),
        cy=float(mtx_left[1, 2]),
        R=np.eye(3, dtype=np.float64),
        t=np.zeros(3, dtype=np.float64),
        distortion=dist_left,
        fundamental_matrix=fmat,
        camera_id="left",
    )
    right = RayCameraModel(
        fx=float(mtx_right[0, 0]),
        fy=float(mtx_right[1, 1]),
        cx=float(mtx_right[0, 2]),
        cy=float(mtx_right[1, 2]),
        R=rmat,
        t=t_ft,
        distortion=dist_right,
        fundamental_matrix=fmat,
        camera_id="right",
    )
    return {"left": left, "right": right}


def _distortion_tuple(values: np.ndarray) -> Optional[Tuple[float, float, float, float, float]]:
    flat: np.ndarray = values.reshape(-1).astype(float)
    if flat.size < 5 or np.allclose(flat[:5], 0.0):
        return None
    return cast(Tuple[float, float, float, float, float], tuple(float(v) for v in flat[:5]))
