"""Tests for StereoRectifier (Phase D).

Builds a synthetic CalibratedStereoGeometry and verifies that rectification
produces row-aligned projections analytically (no rendering needed), plus that
image remapping preserves shape.
"""

from __future__ import annotations

import numpy as np
import pytest

from rectify import StereoRectifier
from stereo.calibrated_stereo import CalibratedStereoGeometry


def _geometry(roll_deg: float = 0.0, width: int = 640, height: int = 480):
    """Canonical horizontal stereo with an optional right-camera roll."""
    focal = 600.0
    k = np.array(
        [[focal, 0, width / 2.0], [0, focal, height / 2.0], [0, 0, 1]],
        dtype=np.float64,
    )
    theta = np.deg2rad(roll_deg)
    rot = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0],
            [np.sin(theta), np.cos(theta), 0],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )
    # 120mm baseline along x (translation of left frame in right coords).
    t = np.array([[-120.0], [0.0], [0.0]], dtype=np.float64)
    zeros = np.zeros(5, dtype=np.float64)
    return CalibratedStereoGeometry(
        mtx_left=k,
        dist_left=zeros,
        mtx_right=k,
        dist_right=zeros,
        R=rot,
        T=t,
        F=np.eye(3),
        img_size=(width, height),
        epipolar_epsilon_px=2.0,
        z_min_ft=1.0,
        z_max_ft=80.0,
    )


def test_from_geometry_builds_maps_and_matrices():
    rect = StereoRectifier.from_geometry(_geometry())
    assert rect.image_size == (640, 480)
    assert rect.P1.shape == (3, 4)
    assert rect.P2.shape == (3, 4)
    assert rect.Q.shape == (4, 4)
    # Each map is (map_x, map_y) at image resolution.
    assert rect._map_left[0].shape == (480, 640)
    assert rect._map_right[0].shape == (480, 640)


def test_rectify_pair_preserves_shape():
    rng = np.random.default_rng(0)
    left = rng.integers(0, 256, size=(480, 640), dtype=np.uint8)
    right = rng.integers(0, 256, size=(480, 640), dtype=np.uint8)
    rect = StereoRectifier.from_geometry(_geometry())
    out_left, out_right = rect.rectify_pair(left, right)
    assert out_left.shape == left.shape
    assert out_right.shape == right.shape


def test_rectified_rows_align_for_canonical_stereo():
    rect = StereoRectifier.from_geometry(_geometry(roll_deg=0.0))
    # A 3D point in front of the rig (mm); both rectified rows should match.
    point = np.array([50.0, 30.0, 3000.0])
    row_left, row_right = rect.rectified_row(point)
    assert abs(row_left - row_right) < 1e-6


def test_rectification_aligns_rows_despite_camera_roll():
    # Even with a 3-degree right-camera roll, rectification co-aligns rows.
    rect = StereoRectifier.from_geometry(_geometry(roll_deg=3.0))
    for point in (
        np.array([0.0, 0.0, 2500.0]),
        np.array([200.0, -150.0, 4000.0]),
        np.array([-180.0, 120.0, 3500.0]),
    ):
        row_left, row_right = rect.rectified_row(point)
        assert abs(row_left - row_right) < 1e-6


def test_alpha_parameter_accepted():
    rect = StereoRectifier.from_geometry(_geometry(), alpha=1.0)
    assert rect.P1.shape == (3, 4)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
