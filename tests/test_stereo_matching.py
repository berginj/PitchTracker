"""Characterization tests for calib.stereo_matching module."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from calib.calibration_io import CornerDetection
from calib.stereo_matching import (
    MIN_CHARUCO_STEREO_CORNERS,
    _match_stereo_pairs,
    _pair_diag,
)


def test_match_charuco_by_corner_id():
    """Stereo matching aligns ChArUco points by corner ID."""
    left_ids = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=np.int32)
    right_ids = np.array([9, 8, 7, 6, 5, 4, 3, 2, 1], dtype=np.int32)
    obj = np.array([[float(i), 0.0, 0.0] for i in left_ids],
                   dtype=np.float32)
    l_img = np.array([[[float(i), 10.0]] for i in left_ids],
                     dtype=np.float32)
    r_obj = np.array([[float(i), 0.0, 0.0] for i in right_ids],
                     dtype=np.float32)
    r_img = np.array([[[float(i), 20.0]] for i in right_ids],
                     dtype=np.float32)

    matched, lp, rp, rej, diag = _match_stereo_pairs(
        [CornerDetection(0, Path("l.png"), obj, l_img, "charuco",
                         left_ids)],
        [CornerDetection(0, Path("r.png"), r_obj, r_img, "charuco",
                         right_ids)],
    )
    assert rej == []
    assert len(matched) == 1
    assert matched[0][:, 0].tolist() == list(range(1, 10))


def test_reject_too_few_shared_charuco():
    ids = np.array([1, 2, 3, 4, 5, 6, 7], dtype=np.int32)
    pts = np.zeros((7, 3), dtype=np.float32)
    img = np.zeros((7, 1, 2), dtype=np.float32)

    matched, _, _, rej, diag = _match_stereo_pairs(
        [CornerDetection(0, Path("l.png"), pts, img, "charuco", ids)],
        [CornerDetection(0, Path("r.png"), pts, img, "charuco", ids)],
    )
    assert matched == []
    assert any("only 7" in m for m in rej)


def test_reject_mixed_detection_types():
    pts = np.zeros((10, 3), dtype=np.float32)
    img = np.zeros((10, 1, 2), dtype=np.float32)

    matched, _, _, rej, diag = _match_stereo_pairs(
        [CornerDetection(0, Path("l.png"), pts, img, "charuco",
                         np.arange(10, dtype=np.int32))],
        [CornerDetection(0, Path("r.png"), pts, img, "checkerboard")],
    )
    assert matched == []
    assert any("mixed" in m for m in rej)


def test_pair_diag_fields():
    pts = np.zeros((5, 3), dtype=np.float32)
    img = np.zeros((5, 1, 2), dtype=np.float32)
    d = _pair_diag(
        0,
        CornerDetection(0, Path("l.png"), pts, img, "charuco"),
        CornerDetection(0, Path("r.png"), pts, img, "charuco"),
        "accepted", "test", 5,
    )
    assert d["status"] == "accepted"
    assert d["shared_corners"] == 5


def test_min_charuco_stereo_corners_value():
    assert MIN_CHARUCO_STEREO_CORNERS == 8
