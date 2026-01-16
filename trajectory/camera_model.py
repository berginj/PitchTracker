"""Camera model for projection and Jacobians."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


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

    def project(self, xyz_ft: np.ndarray) -> np.ndarray:
        point = self.R @ xyz_ft.reshape(3, 1) + self.t.reshape(3, 1)
        x, y, z = point.flatten()
        if z == 0:
            z = 1e-6
        u = self.fx * (x / z) + self.cx
        v = self.fy * (y / z) + self.cy
        if self.distortion is None:
            return np.array([u, v], dtype=float)
        k1, k2, p1, p2, k3 = self.distortion
        xn = x / z
        yn = y / z
        r2 = xn * xn + yn * yn
        radial = 1 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2
        x_dist = xn * radial + 2 * p1 * xn * yn + p2 * (r2 + 2 * xn * xn)
        y_dist = yn * radial + p1 * (r2 + 2 * yn * yn) + 2 * p2 * xn * yn
        return np.array([self.fx * x_dist + self.cx, self.fy * y_dist + self.cy], dtype=float)

    def jacobian_project(self, xyz_ft: np.ndarray) -> np.ndarray:
        eps = 1e-4
        base = self.project(xyz_ft)
        jac = np.zeros((2, 3), dtype=float)
        for i in range(3):
            delta = np.zeros(3, dtype=float)
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
