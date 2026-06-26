"""Targetless coarse stereo rectification (setup step 6).

Estimates the fundamental matrix from matched ORB features and derives
uncalibrated rectifying homographies via ``cv2.stereoRectifyUncalibrated``.
Reports the mean vertical disparity of inlier correspondences before and after
applying the homographies so the operator can see whether rectification
actually helped. This is *coarse* (no metric scale); ChArUco fine-tuning and
full stereo calibration come later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

from calib.stereo_setup._features import detect_and_match, to_gray
from contracts.setup import CoarseRectificationResult
from log_config.logger import get_logger

logger = get_logger(__name__)

_IDENTITY = tuple(float(v) for v in np.eye(3).ravel())


@dataclass(frozen=True)
class RectifyConfig:
    """Thresholds for coarse rectification.

    Attributes:
        max_features: Maximum ORB features per image.
        ransac_thresh_px: RANSAC threshold for fundamental-matrix estimation.
        confidence: RANSAC confidence for fundamental-matrix estimation.
        min_inliers: Minimum F inliers required to derive homographies.
        max_epipolar_error_px: Post-rectification vertical-disparity threshold
            (pixels) below which rectification is considered to pass.
    """

    max_features: int = 1500
    ransac_thresh_px: float = 1.5
    confidence: float = 0.99
    min_inliers: int = 8
    max_epipolar_error_px: float = 2.0


def _mean_vertical_disparity(pts_a: np.ndarray, pts_b: np.ndarray) -> float:
    """Mean absolute difference in y between corresponding points."""
    if pts_a.shape[0] == 0:
        return 0.0
    return float(np.mean(np.abs(pts_a[:, 1] - pts_b[:, 1])))


def _as_tuple(matrix: np.ndarray) -> Tuple[float, ...]:
    return tuple(float(v) for v in np.asarray(matrix, dtype=float).ravel())


def _fail(
    inliers: int,
    before: float,
    recommendation: str,
) -> CoarseRectificationResult:
    return CoarseRectificationResult(
        fundamental_matrix=tuple(0.0 for _ in range(9)),
        left_homography=_IDENTITY,
        right_homography=_IDENTITY,
        epipolar_error_before_px=before,
        epipolar_error_after_px=before,
        inlier_matches=inliers,
        converged=False,
        passed=False,
        recommendation=recommendation,
    )


def coarse_rectify(
    left: np.ndarray,
    right: np.ndarray,
    config: RectifyConfig | None = None,
) -> CoarseRectificationResult:
    """Estimate F and rectifying homographies for a stereo pair.

    Args:
        left: Left frame (grayscale or BGR).
        right: Right frame (grayscale or BGR), synchronized.
        config: Optional thresholds; defaults to :class:`RectifyConfig`.

    Returns:
        A :class:`CoarseRectificationResult`. ``converged`` is True when F and
        the homographies were derived; ``passed`` additionally requires the
        post-rectification epipolar error to be within threshold.
    """
    cfg = config or RectifyConfig()
    gray_left = to_gray(left)
    gray_right = to_gray(right)
    height, width = gray_left.shape[:2]

    _, _, pts_left, pts_right, _ = detect_and_match(gray_left, gray_right, max_features=cfg.max_features)
    if pts_left.shape[0] < cfg.min_inliers:
        return _fail(
            int(pts_left.shape[0]),
            0.0,
            "Too few matches to estimate epipolar geometry; improve overlap " "and focus first.",
        )

    return rectify_from_correspondences(pts_left, pts_right, (width, height), cfg)


def rectify_from_correspondences(
    pts_left: np.ndarray,
    pts_right: np.ndarray,
    image_size: Tuple[int, int],
    config: RectifyConfig | None = None,
) -> CoarseRectificationResult:
    """Estimate F and rectifying homographies from known correspondences.

    Args:
        pts_left: ``(N, 2)`` float left-image points.
        pts_right: ``(N, 2)`` float right-image points (same order).
        image_size: ``(width, height)`` in pixels.
        config: Optional thresholds; defaults to :class:`RectifyConfig`.

    Returns:
        A :class:`CoarseRectificationResult`.
    """
    cfg = config or RectifyConfig()
    width, height = image_size
    pts_left = np.asarray(pts_left, dtype=np.float32).reshape(-1, 2)
    pts_right = np.asarray(pts_right, dtype=np.float32).reshape(-1, 2)
    if pts_left.shape[0] < cfg.min_inliers or pts_left.shape != pts_right.shape:
        return _fail(
            int(pts_left.shape[0]),
            0.0,
            "Too few correspondences to estimate epipolar geometry.",
        )

    fmat, mask = cv2.findFundamentalMat(
        pts_left,
        pts_right,
        cv2.FM_RANSAC,
        cfg.ransac_thresh_px,
        cfg.confidence,
    )
    if fmat is None or mask is None or fmat.shape != (3, 3):
        return _fail(
            0,
            0.0,
            "Fundamental-matrix estimation failed; the views may be " "degenerate (pure rotation or no parallax).",
        )

    mask_bool = mask.ravel().astype(bool)
    inlier_left = pts_left[mask_bool]
    inlier_right = pts_right[mask_bool]
    inliers = int(inlier_left.shape[0])
    before = _mean_vertical_disparity(inlier_left, inlier_right)

    if inliers < cfg.min_inliers:
        return _fail(
            inliers,
            before,
            "Too few inliers after geometric verification to rectify " "reliably.",
        )

    ok, h_left, h_right = cv2.stereoRectifyUncalibrated(
        inlier_left.reshape(-1, 1, 2),
        inlier_right.reshape(-1, 1, 2),
        fmat,
        (width, height),
    )
    if not ok:
        return _fail(
            inliers,
            before,
            "Could not derive rectifying homographies from the estimated " "geometry.",
        )

    warped_left = cv2.perspectiveTransform(inlier_left.reshape(-1, 1, 2), h_left).reshape(-1, 2)
    warped_right = cv2.perspectiveTransform(inlier_right.reshape(-1, 1, 2), h_right).reshape(-1, 2)
    after = _mean_vertical_disparity(warped_left, warped_right)

    passed = after <= cfg.max_epipolar_error_px
    if passed:
        recommendation = "Coarse rectification succeeded."
    else:
        recommendation = (
            "Rectification did not bring rows into alignment within tolerance. "
            "Re-check focus, overlap, and sync, then retry."
        )
    logger.info(
        "Coarse rectification: converged inliers={} before={:.2f}px " "after={:.2f}px passed={}",
        inliers,
        before,
        after,
        passed,
    )
    return CoarseRectificationResult(
        fundamental_matrix=_as_tuple(fmat),
        left_homography=_as_tuple(h_left),
        right_homography=_as_tuple(h_right),
        epipolar_error_before_px=before,
        epipolar_error_after_px=after,
        inlier_matches=inliers,
        converged=True,
        passed=passed,
        recommendation=recommendation,
    )
