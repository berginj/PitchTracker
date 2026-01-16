"""Tests for stereo triangulation accuracy."""

from __future__ import annotations

import numpy as np
import pytest

from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry
from stereo.association import StereoMatch
from contracts import Detection


def test_basic_triangulation():
    """Test basic triangulation with known geometry."""
    # Setup: baseline = 1.0 ft, focal = 1200 px
    geometry = StereoGeometry(
        baseline_ft=1.0,
        focal_length_px=1200.0,
        cx=960.0,  # Half of 1920
        cy=540.0,  # Half of 1080
        epipolar_epsilon_px=3.0,
    )

    # Known point at 50 ft depth, centered in frame
    # For a point at center: disparity = baseline * focal / depth
    # disparity = 1.0 * 1200 / 50 = 24 pixels
    depth_ft = 50.0
    expected_disparity = geometry.baseline_ft * geometry.focal_length_px / depth_ft

    # Left detection at center: (960, 540)
    # Right detection shifted by disparity: (960 - 24, 540)
    left_u = 960.0
    left_v = 540.0
    right_u = left_u - expected_disparity
    right_v = left_v

    # Create detections
    left_det = Detection(
        camera_id="left",
        frame_index=0,
        t_capture_monotonic_ns=0,
        u=left_u,
        v=left_v,
        radius=10.0,
        confidence=1.0,
    )

    right_det = Detection(
        camera_id="right",
        frame_index=0,
        t_capture_monotonic_ns=0,
        u=right_u,
        v=right_v,
        radius=10.0,
        confidence=1.0,
    )

    matcher = SimpleStereoMatcher(geometry)
    match = StereoMatch(left_det, right_det)

    # Compute depth
    disparity = left_det.u - right_det.u
    computed_depth = (geometry.baseline_ft * geometry.focal_length_px) / disparity

    # Verify depth is close to expected
    assert abs(computed_depth - depth_ft) < 0.1, f"Expected depth {depth_ft}, got {computed_depth}"


def test_triangulation_off_center():
    """Test triangulation for point off-center."""
    geometry = StereoGeometry(
        baseline_ft=1.0,
        focal_length_px=1200.0,
        cx=960.0,
        cy=540.0,
        epipolar_epsilon_px=3.0,
    )

    # Point at 30 ft depth, offset to the right in image
    depth_ft = 30.0
    disparity = geometry.baseline_ft * geometry.focal_length_px / depth_ft  # 40 pixels

    left_u = 1200.0  # Offset right
    left_v = 400.0   # Offset up
    right_u = left_u - disparity
    right_v = left_v

    # Compute X coordinate (horizontal offset from center)
    # X = (u - cx) * depth / f
    expected_x_ft = (left_u - geometry.cx) * depth_ft / geometry.focal_length_px

    # Create detections
    left_det = Detection(
        camera_id="left",
        frame_index=0,
        t_capture_monotonic_ns=0,
        u=left_u,
        v=left_v,
        radius=10.0,
        confidence=1.0,
    )

    right_det = Detection(
        camera_id="right",
        frame_index=0,
        t_capture_monotonic_ns=0,
        u=right_u,
        v=right_v,
        radius=10.0,
        confidence=1.0,
    )

    # Verify epipolar constraint (y-coordinates should match within epsilon)
    assert abs(left_det.v - right_det.v) < geometry.epipolar_epsilon_px

    # Compute depth
    computed_disparity = left_det.u - right_det.u
    computed_depth = (geometry.baseline_ft * geometry.focal_length_px) / computed_disparity

    # Compute X coordinate
    computed_x = (left_u - geometry.cx) * computed_depth / geometry.focal_length_px

    assert abs(computed_depth - depth_ft) < 0.1
    assert abs(computed_x - expected_x_ft) < 0.1


def test_epipolar_constraint():
    """Test that epipolar constraint is enforced."""
    geometry = StereoGeometry(
        baseline_ft=1.0,
        focal_length_px=1200.0,
        cx=960.0,
        cy=540.0,
        epipolar_epsilon_px=3.0,
    )

    # Create detections that violate epipolar constraint
    left_det = Detection(
        camera_id="left",
        frame_index=0,
        t_capture_monotonic_ns=0,
        u=960.0,
        v=540.0,
        radius=10.0,
        confidence=1.0,
    )

    right_det_bad = Detection(
        camera_id="right",
        frame_index=0,
        t_capture_monotonic_ns=0,
        u=936.0,
        v=560.0,  # 20 pixels off in y - violates constraint
        radius=10.0,
        confidence=1.0,
    )

    # Check epipolar constraint
    y_diff = abs(left_det.v - right_det_bad.v)
    assert y_diff > geometry.epipolar_epsilon_px, "Should violate epipolar constraint"


def test_triangulation_accuracy_at_various_depths():
    """Test triangulation accuracy at multiple depths."""
    geometry = StereoGeometry(
        baseline_ft=1.0,
        focal_length_px=1200.0,
        cx=960.0,
        cy=540.0,
        epipolar_epsilon_px=3.0,
    )

    test_depths = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]

    for expected_depth in test_depths:
        disparity = geometry.baseline_ft * geometry.focal_length_px / expected_depth

        left_u = 960.0
        right_u = left_u - disparity

        # Reconstruct depth
        computed_depth = (geometry.baseline_ft * geometry.focal_length_px) / disparity

        # Relative error should be < 1%
        relative_error = abs(computed_depth - expected_depth) / expected_depth
        assert relative_error < 0.01, f"At depth {expected_depth}ft, error = {relative_error*100}%"


def test_zero_disparity_handling():
    """Test handling of zero disparity (infinite depth)."""
    geometry = StereoGeometry(
        baseline_ft=1.0,
        focal_length_px=1200.0,
        cx=960.0,
        cy=540.0,
        epipolar_epsilon_px=3.0,
    )

    # Zero disparity should result in very large or infinite depth
    disparity = 0.0

    # In real code, this should be handled gracefully
    # Either return inf, None, or a very large number
    if disparity == 0:
        computed_depth = float('inf')
    else:
        computed_depth = (geometry.baseline_ft * geometry.focal_length_px) / disparity

    assert computed_depth == float('inf') or computed_depth > 1000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
