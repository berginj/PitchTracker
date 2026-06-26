"""Synthetic stereo-pair tests for calib.stereo_setup.

These tests prove the overlap-validation and coarse-rectification logic on
deterministic synthetic image pairs (no hardware). The generator produces a
heavily textured scene with two depth bands (so the fundamental matrix is not
degenerate) and an optional roll that injects vertical disparity for the
rectifier to remove.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from calib.stereo_setup import (
    OverlapConfig,
    RectifyConfig,
    coarse_rectify,
    rectify_from_correspondences,
    validate_overlap,
)
from contracts.setup import (
    OVERLAP_VERDICT_POOR,
    CoarseRectificationResult,
    StereoOverlapResult,
)


def _textured(width: int = 640, height: int = 480, seed: int = 7) -> np.ndarray:
    """Build a high-frequency textured grayscale image rich in ORB corners."""
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    # Add structured shapes so ORB finds stable, repeatable corners.
    for _ in range(120):
        x = int(rng.integers(10, width - 10))
        y = int(rng.integers(10, height - 10))
        r = int(rng.integers(4, 16))
        color = int(rng.integers(0, 256))
        cv2.rectangle(base, (x - r, y - r), (x + r, y + r), color, -1)
    return cv2.GaussianBlur(base, (3, 3), 0)


def _make_stereo_pair(
    dx_far: int = 6,
    dx_near: int = 18,
    roll_deg: float = 0.0,
    seed: int = 7,
):
    """Return (left, right) with two depth bands and an optional right roll.

    The top half is a 'far' band (small disparity), the bottom half a 'near'
    band (large disparity). Differing disparities give the scene real depth so
    the fundamental matrix is well-defined. A roll on the right view injects
    vertical disparity that rectification should remove.
    """
    left = _textured(seed=seed)
    height, width = left.shape
    right = np.zeros_like(left)

    half = height // 2
    # Far band (top): shift left by dx_far.
    m_far = np.float32([[1, 0, -dx_far], [0, 1, 0]])
    far = cv2.warpAffine(left, m_far, (width, height), borderMode=cv2.BORDER_REFLECT)
    # Near band (bottom): shift left by dx_near.
    m_near = np.float32([[1, 0, -dx_near], [0, 1, 0]])
    near = cv2.warpAffine(left, m_near, (width, height), borderMode=cv2.BORDER_REFLECT)

    right[:half] = far[:half]
    right[half:] = near[half:]

    if roll_deg:
        center = (width / 2.0, height / 2.0)
        rot = cv2.getRotationMatrix2D(center, roll_deg, 1.0)
        right = cv2.warpAffine(right, rot, (width, height), borderMode=cv2.BORDER_REFLECT)
    return left, right


# ----------------------------- overlap tests ------------------------------


def test_overlap_identical_pair_is_good():
    img = _textured()
    result = validate_overlap(img, img)
    assert isinstance(result, StereoOverlapResult)
    assert result.passed is True
    assert result.inlier_matches >= 30
    assert result.inlier_ratio > 0.8
    assert result.overlap_score > 0.3


def test_overlap_shifted_stereo_pair_passes():
    left, right = _make_stereo_pair()
    result = validate_overlap(left, right)
    assert result.passed is True
    assert result.inlier_matches >= 12


def test_overlap_unrelated_images_is_poor():
    left = _textured(seed=1)
    right = _textured(seed=999)
    result = validate_overlap(left, right)
    assert result.verdict == OVERLAP_VERDICT_POOR
    assert result.passed is False


def test_overlap_blank_image_reports_too_few_matches():
    blank = np.full((480, 640), 128, dtype=np.uint8)
    result = validate_overlap(blank, blank)
    assert result.passed is False
    assert result.raw_matches < OverlapConfig().min_raw_matches
    assert "feature matches" in result.recommendation.lower()


def test_overlap_accepts_bgr_input():
    gray = _textured()
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    result = validate_overlap(bgr, bgr)
    assert result.passed is True


def test_overlap_result_payload_round_trips():
    img = _textured()
    payload = validate_overlap(img, img).to_payload()
    assert payload["passed"] is True
    assert set(payload).issuperset({"keypoints_left", "inlier_ratio", "overlap_score", "verdict"})


def _project_stereo_correspondences(
    n: int = 200,
    width: int = 640,
    height: int = 480,
    baseline: float = 0.12,
    roll_deg: float = 2.0,
    seed: int = 3,
):
    """Project random 3D points into two calibrated cameras.

    The right camera is translated along x (baseline) and rolled about its
    optical axis by ``roll_deg`` so the unrectified pair has real vertical
    disparity. Depth varies per point so the fundamental matrix is well-defined.

    Returns ``(pts_left, pts_right, (width, height))``.
    """
    rng = np.random.default_rng(seed)
    focal = 600.0
    cx, cy = width / 2.0, height / 2.0
    k = np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1]], dtype=np.float64)

    # 3D points spread in X/Y with varying depth Z (parallax).
    xs = rng.uniform(-1.0, 1.0, n)
    ys = rng.uniform(-0.8, 0.8, n)
    zs = rng.uniform(2.0, 6.0, n)
    pts3d = np.stack([xs, ys, zs], axis=1)

    theta = np.deg2rad(roll_deg)
    rot = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0],
            [np.sin(theta), np.cos(theta), 0],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )
    t = np.array([-baseline, 0.0, 0.0], dtype=np.float64)

    left_cam = (k @ pts3d.T).T
    pts_left = left_cam[:, :2] / left_cam[:, 2:3]

    right_world = (rot @ pts3d.T).T + t
    right_cam = (k @ right_world.T).T
    pts_right = right_cam[:, :2] / right_cam[:, 2:3]

    return (
        pts_left.astype(np.float32),
        pts_right.astype(np.float32),
        (width, height),
    )


# --------------------------- rectification tests ---------------------------


def test_coarse_rectify_converges_on_stereo_pair():
    left, right = _make_stereo_pair()
    result = coarse_rectify(left, right)
    assert isinstance(result, CoarseRectificationResult)
    assert result.converged is True
    assert result.inlier_matches >= RectifyConfig().min_inliers
    assert np.isfinite(result.epipolar_error_after_px)


def test_coarse_rectify_reduces_vertical_disparity():
    # Known projective stereo geometry with a 2-degree right-camera roll.
    pts_left, pts_right, size = _project_stereo_correspondences(roll_deg=2.0)
    result = rectify_from_correspondences(pts_left, pts_right, size)
    assert result.converged is True
    assert result.epipolar_error_before_px > 1.0  # roll injected disparity
    # Rectification brings rows into alignment.
    assert result.epipolar_error_after_px < result.epipolar_error_before_px
    assert result.passed is True


def test_coarse_rectify_fails_on_too_few_matches():
    blank = np.full((480, 640), 128, dtype=np.uint8)
    result = coarse_rectify(blank, blank)
    assert result.converged is False
    assert result.passed is False
    assert result.inlier_matches < RectifyConfig().min_inliers


def test_coarse_rectify_payload_round_trips():
    left, right = _make_stereo_pair()
    payload = coarse_rectify(left, right).to_payload()
    assert "fundamental_matrix" in payload
    assert len(payload["fundamental_matrix"]) == 9
    assert "left_homography" in payload and "right_homography" in payload


def test_coarse_rectify_identity_homography_on_failure():
    blank = np.full((480, 640), 128, dtype=np.uint8)
    result = coarse_rectify(blank, blank)
    # Failure path returns identity homographies, not garbage.
    assert result.left_homography == tuple(float(v) for v in np.eye(3).ravel())
    assert result.right_homography == tuple(float(v) for v in np.eye(3).ravel())


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
