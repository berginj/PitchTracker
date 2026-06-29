"""Tests for stereo triangulation uncertainty helpers."""

from __future__ import annotations

import math

import pytest

from stereo import depth_only_covariance, estimate_rectified_depth_uncertainty, quality_from_depth_sigma


def test_rectified_depth_uncertainty_matches_known_depth_formula() -> None:
    result = estimate_rectified_depth_uncertainty(
        left_u_px=640.0,
        right_u_px=601.0,
        focal_length_px=1200.0,
        baseline_ft=1.625,
        pixel_sigma_px=0.5,
        baseline_sigma_ft=0.0,
    )

    assert result.disparity_px == 39.0
    assert result.depth_ft == 50.0
    assert result.disparity_sigma_px == pytest.approx(math.sqrt(2.0) * 0.5)
    assert result.depth_sigma_ft == pytest.approx(0.9065, abs=0.001)


def test_rectified_depth_uncertainty_grows_at_longer_pitch_distances() -> None:
    near = estimate_rectified_depth_uncertainty(
        left_u_px=640.0,
        right_u_px=591.25,
        focal_length_px=1200.0,
        baseline_ft=1.625,
        pixel_sigma_px=0.5,
    )
    far = estimate_rectified_depth_uncertainty(
        left_u_px=640.0,
        right_u_px=607.769,
        focal_length_px=1200.0,
        baseline_ft=1.625,
        pixel_sigma_px=0.5,
    )

    assert near.depth_ft == pytest.approx(40.0, abs=0.01)
    assert far.depth_ft == pytest.approx(60.5, abs=0.01)
    assert far.depth_sigma_ft > near.depth_sigma_ft * 2.0


def test_rectified_depth_uncertainty_includes_baseline_uncertainty() -> None:
    pixel_only = estimate_rectified_depth_uncertainty(
        left_u_px=640.0,
        right_u_px=601.0,
        focal_length_px=1200.0,
        baseline_ft=1.625,
        pixel_sigma_px=0.5,
        baseline_sigma_ft=0.0,
    )
    with_baseline = estimate_rectified_depth_uncertainty(
        left_u_px=640.0,
        right_u_px=601.0,
        focal_length_px=1200.0,
        baseline_ft=1.625,
        pixel_sigma_px=0.5,
        baseline_sigma_ft=0.02,
    )

    assert with_baseline.depth_sigma_from_baseline_ft == pytest.approx(50.0 * 0.02 / 1.625)
    assert with_baseline.depth_sigma_ft > pixel_only.depth_sigma_ft


def test_depth_sigma_quality_mapping_and_covariance() -> None:
    assert quality_from_depth_sigma(1.5, 3.0) == 1.0
    assert quality_from_depth_sigma(6.0, 3.0) == 0.5
    assert quality_from_depth_sigma(6.0, 0.0) == 1.0
    assert depth_only_covariance(2.5)[2][2] == 6.25


@pytest.mark.parametrize(
    "kwargs",
    [
        {"left_u_px": 640.0, "right_u_px": 640.0},
        {"left_u_px": 640.0, "right_u_px": 600.0, "focal_length_px": 0.0},
        {"left_u_px": 640.0, "right_u_px": 600.0, "baseline_ft": 0.0},
        {"left_u_px": 640.0, "right_u_px": 600.0, "pixel_sigma_px": -0.1},
        {"left_u_px": 640.0, "right_u_px": 600.0, "baseline_sigma_ft": -0.1},
    ],
)
def test_rectified_depth_uncertainty_rejects_invalid_inputs(kwargs: dict[str, float]) -> None:
    params = {
        "left_u_px": 640.0,
        "right_u_px": 600.0,
        "focal_length_px": 1200.0,
        "baseline_ft": 1.625,
    }
    params.update(kwargs)

    with pytest.raises(ValueError):
        estimate_rectified_depth_uncertainty(**params)
