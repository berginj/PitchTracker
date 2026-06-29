"""Synthetic calibrated-stereo error-budget tests.

These tests intentionally validate the production calibrated stereo matcher
against known 3D points before detector quality enters the problem.
"""

from __future__ import annotations

import numpy as np

from contracts import Detection
from stereo.calibrated_stereo import CalibratedStereoMatcher
from tests.synthetic_stereo_geometry import (
    make_misaligned_geometry,
    make_rectified_geometry,
    project_points,
    triangulate_projected_point,
)


PITCH_LANE_POINTS_FT = [
    (0.0, 2.5, 40.0),  # softball-ish release distance
    (-0.8, 3.1, 50.0),
    (0.6, 2.8, 60.5),  # baseball mound distance
    (1.1, 3.6, 55.0),  # off-axis arm-side location
    (-1.2, 1.7, 3.0),  # near plate
]


def test_synthetic_calibrated_stereo_reconstructs_known_pitch_lane_points() -> None:
    geometry = make_rectified_geometry()
    matcher = CalibratedStereoMatcher(geometry)

    for frame_index, projected in enumerate(project_points(geometry, PITCH_LANE_POINTS_FT)):
        match, obs = triangulate_projected_point(matcher, projected, frame_index=frame_index)
        actual = np.array([obs.X, obs.Y, obs.Z], dtype=np.float64)
        error_ft = np.linalg.norm(actual - projected.xyz_ft)

        assert match.epipolar_error_px < 1e-6
        assert error_ft < 0.02
        assert obs.confidence == 1.0


def test_synthetic_calibrated_stereo_has_explicit_half_pixel_noise_budget() -> None:
    geometry = make_rectified_geometry(epipolar_epsilon_px=2.0)
    matcher = CalibratedStereoMatcher(geometry)

    for frame_index, projected in enumerate(project_points(geometry, PITCH_LANE_POINTS_FT[:-1])):
        _, obs = triangulate_projected_point(
            matcher,
            projected,
            left_noise_px=(0.25, -0.10),
            right_noise_px=(-0.25, 0.10),
            frame_index=frame_index,
        )
        actual = np.array([obs.X, obs.Y, obs.Z], dtype=np.float64)
        absolute_error_ft = np.abs(actual - projected.xyz_ft)

        assert absolute_error_ft[0] < 0.20
        assert absolute_error_ft[1] < 0.20
        assert absolute_error_ft[2] < 1.75
        assert obs.confidence == 1.0


def test_synthetic_geometry_exposes_baseline_scale_errors() -> None:
    true_geometry = make_rectified_geometry(baseline_ft=1.625)
    wrong_geometry = make_rectified_geometry(baseline_ft=0.8125)
    matcher = CalibratedStereoMatcher(wrong_geometry)
    projected = project_points(true_geometry, [(0.0, 2.5, 50.0)])[0]

    _, obs = triangulate_projected_point(matcher, projected)

    assert abs(obs.Z - 50.0) > 20.0
    assert obs.confidence == 1.0


def test_synthetic_full_matrix_geometry_handles_imperfect_camera_alignment() -> None:
    geometry = make_misaligned_geometry()
    matcher = CalibratedStereoMatcher(geometry)

    for frame_index, projected in enumerate(project_points(geometry, PITCH_LANE_POINTS_FT[:-1])):
        match, obs = triangulate_projected_point(matcher, projected, frame_index=frame_index)
        actual = np.array([obs.X, obs.Y, obs.Z], dtype=np.float64)
        error_ft = np.linalg.norm(actual - projected.xyz_ft)

        assert match.epipolar_error_px < 1e-6
        assert error_ft < 0.03
        assert obs.confidence == 1.0


def test_synthetic_full_matrix_geometry_rejects_bad_epipolar_pair() -> None:
    geometry = make_misaligned_geometry(epipolar_epsilon_px=1.0)
    matcher = CalibratedStereoMatcher(geometry)
    projected = project_points(geometry, [(0.0, 2.5, 50.0)])[0]

    match, _ = triangulate_projected_point(matcher, projected)
    assert match.epipolar_error_px < 1e-6

    shifted = projected.right_uv.copy()
    shifted[1] += 12.0

    left = Detection("left", 0, 0, float(projected.left_uv[0]), float(projected.left_uv[1]), 4.0, 1.0)
    right = Detection("right", 0, 0, float(shifted[0]), float(shifted[1]), 4.0, 1.0)

    assert matcher.match(left, right) is None


def test_synthetic_timestamp_offset_is_applied_to_calibrated_pairs() -> None:
    geometry = make_misaligned_geometry(time_sync_offset_ns=-5_000_000)
    matcher = CalibratedStereoMatcher(geometry)
    projected = project_points(geometry, [(0.0, 2.5, 50.0)])[0]

    _, obs = triangulate_projected_point(
        matcher,
        projected,
        left_t_ns=100_000_000,
        right_t_ns=105_000_000,
    )
    paired_ns, applied = matcher.pair_timestamp(100_000_000, 105_000_000)

    assert applied is True
    assert paired_ns == 100_000_000
    assert obs.t_ns == 100_000_000
