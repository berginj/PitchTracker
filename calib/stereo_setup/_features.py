"""Shared ORB feature-matching helpers for stereo setup.

Kept separate so :mod:`overlap` and :mod:`rectify` use identical, well-tested
matching behavior. All functions are pure and operate on numpy arrays.
"""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from log_config.logger import get_logger

logger = get_logger(__name__)


def to_gray(image: np.ndarray) -> np.ndarray:
    """Return a single-channel uint8 view of ``image``.

    Accepts grayscale (HxW) or BGR/BGRA (HxWxC) arrays.
    """
    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    elif image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError(f"Unsupported image shape {image.shape!r}")
    if gray.dtype != np.uint8:
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return gray


def detect_and_match(
    left: np.ndarray,
    right: np.ndarray,
    max_features: int = 1500,
    min_keypoints: int = 10,
) -> Tuple[int, int, np.ndarray, np.ndarray, np.ndarray]:
    """Detect ORB keypoints in both images and cross-check match them.

    Args:
        left: Left grayscale image.
        right: Right grayscale image.
        max_features: Maximum ORB features per image.
        min_keypoints: Minimum keypoints required in each image to attempt a
            match.

    Returns:
        Tuple ``(n_kp_left, n_kp_right, pts_left, pts_right, match_distances)``
        where the point arrays are ``float32`` of shape ``(N, 2)`` and
        ``match_distances`` holds the per-match Hamming descriptor distance.
        Point arrays are empty when matching is not possible.
    """
    orb = cv2.ORB_create(nfeatures=max_features)
    kp_left, des_left = orb.detectAndCompute(left, None)
    kp_right, des_right = orb.detectAndCompute(right, None)

    n_left = len(kp_left) if kp_left is not None else 0
    n_right = len(kp_right) if kp_right is not None else 0

    empty = np.empty((0, 2), dtype=np.float32)
    if des_left is None or des_right is None:
        return n_left, n_right, empty, empty, np.empty((0,), dtype=np.float32)
    if n_left < min_keypoints or n_right < min_keypoints:
        return n_left, n_right, empty, empty, np.empty((0,), dtype=np.float32)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des_left, des_right)
    if not matches:
        return n_left, n_right, empty, empty, np.empty((0,), dtype=np.float32)

    matches = sorted(matches, key=lambda m: m.distance)
    pts_left = np.float32([kp_left[m.queryIdx].pt for m in matches])
    pts_right = np.float32([kp_right[m.trainIdx].pt for m in matches])
    distances = np.float32([m.distance for m in matches])
    return n_left, n_right, pts_left, pts_right, distances


def convex_hull_fraction(points: np.ndarray, width: int, height: int) -> float:
    """Return the fraction of the image area covered by the convex hull.

    Used as a cheap proxy for shared field-of-view extent. Returns 0.0 when
    there are too few points to form a polygon.
    """
    if points.shape[0] < 3 or width <= 0 or height <= 0:
        return 0.0
    hull = cv2.convexHull(points.astype(np.float32))
    area = float(cv2.contourArea(hull))
    frac = area / float(width * height)
    return max(0.0, min(1.0, frac))
