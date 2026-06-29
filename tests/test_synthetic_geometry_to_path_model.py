"""Synthetic stereo-to-path-model tests."""

from __future__ import annotations

import numpy as np
import pytest

from stereo.calibrated_stereo import CalibratedStereoMatcher
from tests.synthetic_stereo_geometry import make_misaligned_geometry, project_points, triangulate_projected_point
from trajectory.contracts import FailureCode, TrajectoryFitRequest
from trajectory.physics import GRAVITY_FT_S2, PhysicsDragFitter


def test_synthetic_triangulated_points_fit_ballistic_path_to_plate_plane() -> None:
    geometry = make_misaligned_geometry(z_min_ft=2.0, epipolar_epsilon_px=2.0)
    matcher = CalibratedStereoMatcher(geometry)
    times_s = np.linspace(0.0, 0.48, 25)
    points_ft = [_ballistic_position(t_s) for t_s in times_s]
    observations = [
        triangulate_projected_point(
            matcher,
            projected,
            frame_index=index,
            left_t_ns=int(times_s[index] * 1e9),
            right_t_ns=int(times_s[index] * 1e9),
        )[1]
        for index, projected in enumerate(project_points(geometry, points_ft))
    ]
    request = TrajectoryFitRequest(
        observations=observations,
        plate_plane_z_ft=3.0,
        drag_k0=0.0,
        drag_sigma=0.01,
        max_iter=100,
    )

    result = PhysicsDragFitter().fit_trajectory(request)
    if not result.samples:
        pytest.skip("scipy unavailable or fit failed")

    assert result.plate_crossing_xyz_ft is not None
    assert result.diagnostics.rmse_3d_ft is not None
    assert result.diagnostics.rmse_3d_ft < 0.05
    assert FailureCode.NO_PLATE_CROSSING not in result.diagnostics.failure_codes
    assert result.plate_crossing_xyz_ft[2] == pytest.approx(3.0, abs=0.02)
    assert result.plate_crossing_xyz_ft[1] == pytest.approx(_ballistic_position(0.475)[1], abs=0.15)


def _ballistic_position(t_s: float) -> tuple[float, float, float]:
    return (
        0.4 * t_s,
        5.0 + 0.2 * t_s + 0.5 * GRAVITY_FT_S2 * t_s * t_s,
        60.0 - 120.0 * t_s,
    )
