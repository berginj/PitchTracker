"""Stereo overlap / feature-match validation (setup step 5).

Verifies that the left and right cameras actually see the same scene by
matching ORB features across a synchronized pair and geometrically verifying
the matches with a homography + RANSAC. The resulting :class:`StereoOverlapResult`
gates coarse rectification: there is no point estimating epipolar geometry if
the two views barely overlap.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from calib.stereo_setup._features import (
    convex_hull_fraction,
    detect_and_match,
    to_gray,
)
from contracts.setup import (
    OVERLAP_VERDICT_GOOD,
    OVERLAP_VERDICT_POOR,
    OVERLAP_VERDICT_WARN,
    StereoOverlapResult,
)
from log_config.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class OverlapConfig:
    """Thresholds for overlap validation.

    Attributes:
        max_features: Maximum ORB features per image.
        ransac_reproj_px: RANSAC reprojection threshold for homography inliers.
        min_raw_matches: Minimum descriptor matches to attempt verification.
        good_inliers: Inlier count at/above which overlap can be GOOD.
        warn_inliers: Inlier count at/above which overlap can be WARN.
        good_inlier_ratio: Inlier ratio required for a GOOD verdict.
        warn_inlier_ratio: Inlier ratio required for a WARN verdict.
        good_overlap_score: Hull-coverage fraction required for a GOOD verdict.
    """

    max_features: int = 1500
    ransac_reproj_px: float = 3.0
    min_raw_matches: int = 12
    good_inliers: int = 30
    warn_inliers: int = 12
    good_inlier_ratio: float = 0.5
    warn_inlier_ratio: float = 0.25
    good_overlap_score: float = 0.25


def _fail(
    n_left: int,
    n_right: int,
    raw: int,
    recommendation: str,
) -> StereoOverlapResult:
    return StereoOverlapResult(
        keypoints_left=n_left,
        keypoints_right=n_right,
        raw_matches=raw,
        inlier_matches=0,
        inlier_ratio=0.0,
        overlap_score=0.0,
        mean_match_distance_px=0.0,
        verdict=OVERLAP_VERDICT_POOR,
        passed=False,
        recommendation=recommendation,
    )


def validate_overlap(
    left: np.ndarray,
    right: np.ndarray,
    config: OverlapConfig | None = None,
) -> StereoOverlapResult:
    """Validate that ``left`` and ``right`` share a usable field of view.

    Args:
        left: Left frame (grayscale or BGR).
        right: Right frame (grayscale or BGR), same scene, synchronized.
        config: Optional thresholds; defaults to :class:`OverlapConfig`.

    Returns:
        A :class:`StereoOverlapResult`. ``passed`` is True for GOOD or WARN.
    """
    cfg = config or OverlapConfig()
    gray_left = to_gray(left)
    gray_right = to_gray(right)
    height, width = gray_left.shape[:2]

    n_left, n_right, pts_left, pts_right, distances = detect_and_match(
        gray_left, gray_right, max_features=cfg.max_features
    )
    raw = int(pts_left.shape[0])
    if raw < cfg.min_raw_matches:
        return _fail(
            n_left,
            n_right,
            raw,
            "Too few feature matches between views; check that both cameras " "see the same scene and are in focus.",
        )

    homography, mask = cv2.findHomography(pts_left, pts_right, cv2.RANSAC, cfg.ransac_reproj_px)
    if homography is None or mask is None:
        return _fail(
            n_left,
            n_right,
            raw,
            "Could not geometrically verify overlap; views may be unrelated.",
        )

    mask_bool = mask.ravel().astype(bool)
    inlier_matches = int(mask_bool.sum())
    inlier_ratio = inlier_matches / float(raw)

    inlier_left = pts_left[mask_bool]
    inlier_right = pts_right[mask_bool]
    overlap_score = convex_hull_fraction(inlier_left, width, height)

    if inlier_matches >= 1:
        projected = cv2.perspectiveTransform(inlier_left.reshape(-1, 1, 2), homography).reshape(-1, 2)
        residuals = np.linalg.norm(projected - inlier_right, axis=1)
        mean_match_distance_px = float(np.mean(residuals))
    else:
        mean_match_distance_px = 0.0

    if (
        inlier_matches >= cfg.good_inliers
        and inlier_ratio >= cfg.good_inlier_ratio
        and overlap_score >= cfg.good_overlap_score
    ):
        verdict = OVERLAP_VERDICT_GOOD
        recommendation = "Stereo overlap is good."
    elif inlier_matches >= cfg.warn_inliers and inlier_ratio >= cfg.warn_inlier_ratio:
        verdict = OVERLAP_VERDICT_WARN
        recommendation = (
            "Overlap is marginal. Consider reducing camera toe-in or adding "
            "scene texture for a more reliable calibration."
        )
    else:
        verdict = OVERLAP_VERDICT_POOR
        recommendation = (
            "Insufficient shared field of view. Re-aim the cameras so they " "frame the same area before calibrating."
        )

    passed = verdict in (OVERLAP_VERDICT_GOOD, OVERLAP_VERDICT_WARN)
    logger.info(
        "Overlap validation: verdict={} inliers={}/{} ratio={:.2f} score={:.2f}",
        verdict,
        inlier_matches,
        raw,
        inlier_ratio,
        overlap_score,
    )
    return StereoOverlapResult(
        keypoints_left=n_left,
        keypoints_right=n_right,
        raw_matches=raw,
        inlier_matches=inlier_matches,
        inlier_ratio=inlier_ratio,
        overlap_score=overlap_score,
        mean_match_distance_px=mean_match_distance_px,
        verdict=verdict,
        passed=passed,
        recommendation=recommendation,
    )
