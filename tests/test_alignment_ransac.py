"""Tests for RANSAC inlier filtering in the camera-alignment feature matcher."""

import numpy as np

from analysis.camera_alignment_internals import _ransac_filter


def _make_inlier_pair(n: int, shift_x: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    """A clean horizontally-shifted (stereo-like) correspondence set."""
    rng = np.random.default_rng(0)
    pts1 = rng.uniform(0, 640, size=(n, 2)).astype(np.float32)
    pts2 = pts1.copy()
    pts2[:, 0] += shift_x
    return pts1, pts2


def test_ransac_filter_passes_through_when_too_few_points():
    pts1, pts2 = _make_inlier_pair(5)
    out1, out2 = _ransac_filter(pts1, pts2)
    assert out1.shape == pts1.shape
    assert out2.shape == pts2.shape


def test_ransac_filter_keeps_clean_inliers():
    pts1, pts2 = _make_inlier_pair(60)
    out1, out2 = _ransac_filter(pts1, pts2)
    # A consistent geometric transform should retain (nearly) all points.
    assert out1.shape[0] >= 55
    assert out1.shape == out2.shape


def test_ransac_filter_removes_gross_outliers():
    pts1, pts2 = _make_inlier_pair(60)
    rng = np.random.default_rng(1)
    # Corrupt a quarter of the matches with random, geometry-violating targets.
    n_bad = 15
    bad_idx = rng.choice(pts2.shape[0], size=n_bad, replace=False)
    pts2[bad_idx] = rng.uniform(0, 640, size=(n_bad, 2)).astype(np.float32)

    out1, out2 = _ransac_filter(pts1, pts2)
    # Filtered set should be smaller than the corrupted input but still usable.
    assert out1.shape[0] < pts1.shape[0]
    assert out1.shape[0] >= 12
    assert out1.shape == out2.shape


def test_ransac_filter_falls_back_when_no_consensus():
    rng = np.random.default_rng(2)
    pts1 = rng.uniform(0, 640, size=(40, 2)).astype(np.float32)
    pts2 = rng.uniform(0, 640, size=(40, 2)).astype(np.float32)
    out1, out2 = _ransac_filter(pts1, pts2)
    # No consistent geometry -> fall back to the original points, never empty.
    assert out1.shape[0] >= 12
    assert out1.shape == out2.shape
