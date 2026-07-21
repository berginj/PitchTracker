"""Rigid transform from the left-camera coordinate frame to field coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class FieldTransform:
    matrix_4x4: tuple[tuple[float, float, float, float], ...]
    rms_residual_ft: float
    fixture_id: str
    max_rms_residual_ft: float = 0.1

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix_4x4, dtype=float)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
            raise ValueError("matrix_4x4 must be a finite 4x4 matrix")
        if not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-6):
            raise ValueError("field transform must be an affine rigid transform")
        rotation = matrix[:3, :3]
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5):
            raise ValueError("field transform rotation must be orthonormal")
        if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-5):
            raise ValueError("field transform rotation must have determinant +1")
        if not np.isfinite(self.rms_residual_ft) or self.rms_residual_ft < 0:
            raise ValueError("rms_residual_ft must be finite and non-negative")
        if not np.isfinite(self.max_rms_residual_ft) or self.max_rms_residual_ft <= 0:
            raise ValueError("max_rms_residual_ft must be finite and positive")

    @property
    def passes_residual_gate(self) -> bool:
        return self.rms_residual_ft <= self.max_rms_residual_ft

    def apply(self, xyz_camera_ft: Iterable[float]) -> tuple[float, float, float]:
        point = np.asarray(tuple(xyz_camera_ft), dtype=float)
        if point.shape != (3,):
            raise ValueError("point must have three coordinates")
        transformed = np.asarray(self.matrix_4x4) @ np.append(point, 1.0)
        return tuple(float(value) for value in transformed[:3])

    def to_payload(self) -> dict[str, object]:
        return {
            "matrix_4x4": [list(row) for row in self.matrix_4x4],
            "rms_residual_ft": self.rms_residual_ft,
            "fixture_id": self.fixture_id,
            "max_rms_residual_ft": self.max_rms_residual_ft,
        }


def estimate_field_transform(
    camera_points_ft: Iterable[Iterable[float]],
    field_points_ft: Iterable[Iterable[float]],
    *,
    fixture_id: str,
    max_rms_residual_ft: float = 0.1,
) -> FieldTransform:
    """Estimate a proper rigid transform with the Kabsch algorithm."""
    source = np.asarray(tuple(tuple(point) for point in camera_points_ft), dtype=float)
    target = np.asarray(tuple(tuple(point) for point in field_points_ft), dtype=float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("camera and field points must have matching Nx3 shapes")
    if source.shape[0] < 3:
        raise ValueError("at least three fixture points are required")
    if np.linalg.matrix_rank(source - source.mean(axis=0)) < 2:
        raise ValueError("fixture points must not be collinear")

    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[-1, :] *= -1
        rotation = vt.T @ u.T
    translation = target_center - rotation @ source_center

    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    predicted = (rotation @ source.T).T + translation
    rms = float(np.sqrt(np.mean(np.sum((predicted - target) ** 2, axis=1))))
    rows = tuple(tuple(float(value) for value in row) for row in matrix)
    return FieldTransform(rows, rms, fixture_id, max_rms_residual_ft)


__all__ = ["FieldTransform", "estimate_field_transform"]
