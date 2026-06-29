"""Stereo geometry uncertainty helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Tuple


@dataclass(frozen=True)
class RectifiedStereoUncertainty:
    disparity_px: float
    depth_ft: float
    disparity_sigma_px: float
    baseline_sigma_ft: float
    depth_sigma_ft: float
    depth_sigma_from_pixels_ft: float
    depth_sigma_from_baseline_ft: float


def estimate_rectified_depth_uncertainty(
    *,
    left_u_px: float,
    right_u_px: float,
    focal_length_px: float,
    baseline_ft: float,
    pixel_sigma_px: float = 0.5,
    baseline_sigma_ft: float = 0.0,
) -> RectifiedStereoUncertainty:
    """Estimate depth uncertainty for rectified stereo using first-order propagation."""
    disparity_px = float(left_u_px - right_u_px)
    if not isfinite(disparity_px) or abs(disparity_px) <= 1e-9:
        raise ValueError("Disparity must be finite and non-zero.")
    if focal_length_px <= 0.0:
        raise ValueError("Focal length must be positive.")
    if baseline_ft <= 0.0:
        raise ValueError("Baseline must be positive.")
    if pixel_sigma_px < 0.0:
        raise ValueError("Pixel sigma must be non-negative.")
    if baseline_sigma_ft < 0.0:
        raise ValueError("Baseline sigma must be non-negative.")

    depth_ft = focal_length_px * baseline_ft / disparity_px
    disparity_sigma_px = sqrt(2.0) * pixel_sigma_px
    depth_sigma_from_pixels_ft = abs(depth_ft / disparity_px) * disparity_sigma_px
    depth_sigma_from_baseline_ft = abs(depth_ft / baseline_ft) * baseline_sigma_ft
    depth_sigma_ft = sqrt(depth_sigma_from_pixels_ft**2 + depth_sigma_from_baseline_ft**2)
    return RectifiedStereoUncertainty(
        disparity_px=disparity_px,
        depth_ft=depth_ft,
        disparity_sigma_px=disparity_sigma_px,
        baseline_sigma_ft=baseline_sigma_ft,
        depth_sigma_ft=depth_sigma_ft,
        depth_sigma_from_pixels_ft=depth_sigma_from_pixels_ft,
        depth_sigma_from_baseline_ft=depth_sigma_from_baseline_ft,
    )


def quality_from_depth_sigma(depth_sigma_ft: float, full_confidence_sigma_ft: float) -> float:
    """Map depth uncertainty to a bounded quality multiplier."""
    if full_confidence_sigma_ft <= 0.0:
        return 1.0
    if depth_sigma_ft <= full_confidence_sigma_ft:
        return 1.0
    return max(0.0, min(1.0, full_confidence_sigma_ft / depth_sigma_ft))


def depth_only_covariance(
    depth_sigma_ft: float,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    variance = float(depth_sigma_ft * depth_sigma_ft)
    return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, variance))
