"""Geometry validation and quality assessment for stereo calibration."""

from __future__ import annotations

from typing import List

import cv2
import numpy as np

MIN_BASELINE_FT = 0.02
MAX_STEREO_RMS_PX = 50.0


def _validate_stereo_geometry(
    rms_error: float, baseline_ft: float, fmat: np.ndarray,
) -> None:
    """Reject degenerate stereo solutions before they reach config/disk.

    Raises:
        CalibrationExecutionError: if the geometry is non-finite, the baseline
            is implausibly small, or the RMS reprojection error is absurd.
    """
    from exceptions import CalibrationExecutionError

    if not np.isfinite(rms_error) or rms_error > MAX_STEREO_RMS_PX:
        raise CalibrationExecutionError(
            f"Stereo calibration RMS error is implausible ({rms_error}); the "
            "solve did not converge. Recapture with better board coverage."
        )
    if not np.isfinite(baseline_ft) or abs(baseline_ft) < MIN_BASELINE_FT:
        raise CalibrationExecutionError(
            f"Estimated baseline {baseline_ft:.4f} ft is too small; the "
            "cameras appear coincident or the geometry is degenerate."
        )
    if fmat is None or not np.all(
        np.isfinite(np.asarray(fmat, dtype=np.float64))
    ):
        raise CalibrationExecutionError(
            "Fundamental matrix is non-finite; stereo geometry is degenerate."
        )


def _compute_per_image_errors(
    objpoints: List[np.ndarray],
    left_img: List[np.ndarray],
    right_img: List[np.ndarray],
    mtx_left: np.ndarray,
    dist_left: np.ndarray,
    mtx_right: np.ndarray,
    dist_right: np.ndarray,
    R: np.ndarray,
    T: np.ndarray,
) -> List[dict]:
    """Calculate reprojection error for each calibration image pair."""
    errors = []
    for obj_pts, left_pts, right_pts in zip(objpoints, left_img, right_img):
        left_pts_2d = np.asarray(left_pts, dtype=np.float32).reshape(-1, 2)
        right_pts_2d = np.asarray(right_pts, dtype=np.float32).reshape(-1, 2)
        ok, rvec_left, tvec_left = cv2.solvePnP(
            np.asarray(obj_pts, dtype=np.float32),
            left_pts_2d, mtx_left, dist_left,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            errors.append({
                "left_rms": float("inf"),
                "right_rms": float("inf"),
                "combined_rms": float("inf"),
            })
            continue

        left_projected, _ = cv2.projectPoints(
            obj_pts, rvec_left, tvec_left, mtx_left, dist_left,
        )
        left_error = np.sqrt(
            np.mean((left_pts_2d - left_projected.reshape(-1, 2)) ** 2)
        )

        rmat_left, _ = cv2.Rodrigues(rvec_left)
        rmat_right = R @ rmat_left
        tvec_right = R @ tvec_left + T
        rvec_right, _ = cv2.Rodrigues(rmat_right)
        right_projected, _ = cv2.projectPoints(
            obj_pts, rvec_right, tvec_right, mtx_right, dist_right,
        )
        right_error = np.sqrt(
            np.mean((right_pts_2d - right_projected.reshape(-1, 2)) ** 2)
        )

        combined_error = np.sqrt(left_error**2 + right_error**2)
        errors.append({
            "left_rms": float(left_error),
            "right_rms": float(right_error),
            "combined_rms": float(combined_error),
        })

    return errors


def _rate_calibration_quality(
    rms_error: float, num_images: int,
) -> dict:
    """Rate full calibration quality and provide recommendations."""
    EXCELLENT_RMS = 0.5
    GOOD_RMS = 1.0
    ACCEPTABLE_RMS = 2.0
    MIN_IMAGES_GOOD = 15
    MIN_IMAGES_ACCEPTABLE = 10

    recommendations: list[str] = []

    if rms_error < EXCELLENT_RMS and num_images >= MIN_IMAGES_GOOD:
        rating, emoji = "EXCELLENT", "🟢"
        description = ("Outstanding calibration! Ready for high-accuracy "
                       "tracking.")
    elif rms_error < GOOD_RMS and num_images >= MIN_IMAGES_GOOD:
        rating, emoji = "GOOD", "🟢"
        description = "Good calibration. Suitable for most tracking needs."
    elif rms_error < ACCEPTABLE_RMS and num_images >= MIN_IMAGES_ACCEPTABLE:
        rating, emoji = "ACCEPTABLE", "🟡"
        description = ("Acceptable calibration. Consider recalibrating for "
                       "better accuracy.")
        if num_images < MIN_IMAGES_GOOD:
            recommendations.append(
                f"• Capture {MIN_IMAGES_GOOD - num_images} more images "
                "for better quality"
            )
        recommendations.append(
            "• Cover full tracking volume with varied poses"
        )
    else:
        rating, emoji = "POOR", "🔴"
        description = ("Poor calibration. Please recalibrate for reliable "
                       "tracking.")

    if rms_error > 1.0:
        recommendations.extend([
            "• Hold ChArUco board steadier during capture",
            "• Ensure ChArUco board is perfectly flat (no warping)",
            "• Check camera focus is sharp",
            "• Improve lighting (even, no shadows or glare)",
        ])

    if num_images < MIN_IMAGES_ACCEPTABLE:
        recommendations.append(
            f"⚠️  Critical: Need at least {MIN_IMAGES_ACCEPTABLE} images "
            f"(have {num_images})"
        )
        recommendations.append(
            "• Recapture with ChArUco board visible in BOTH cameras"
        )
    elif num_images < MIN_IMAGES_GOOD:
        recommendations.append(
            f"• Capture {MIN_IMAGES_GOOD - num_images} more images "
            "for better quality"
        )

    if rms_error > 2.0:
        recommendations.extend([
            "• Try recalibrating from scratch",
            "• Verify ChArUco board dimensions are correct "
            "(measure square size)",
            "• Check for lens distortion or damage",
            "• Ensure ChArUco board pattern size matches actual board "
            "(count squares)",
        ])

    if (MIN_IMAGES_ACCEPTABLE <= num_images < MIN_IMAGES_GOOD
            or rms_error > GOOD_RMS):
        recommendations.append(
            "• Vary ChArUco board positions: center, corners, near, far, "
            "tilted"
        )

    return {
        "rating": rating,
        "emoji": emoji,
        "description": description,
        "rms_error_px": float(rms_error),
        "num_images": num_images,
        "recommendations": recommendations,
    }


def _rate_quick_calibration_quality(
    rms_error: float, num_images: int,
) -> dict:
    """Rate quick calibration quality with adjusted thresholds."""
    GOOD_RMS = 2.0
    ACCEPTABLE_RMS = 3.0
    MIN_IMAGES = 3
    RECOMMENDED_IMAGES = 5

    recommendations: list[str] = []

    if rms_error < GOOD_RMS and num_images >= RECOMMENDED_IMAGES:
        rating, emoji = "GOOD", "🟢"
        description = ("Good quick calibration. Estimated 90-95% accuracy "
                       "of full calibration.")
    elif rms_error < ACCEPTABLE_RMS and num_images >= MIN_IMAGES:
        rating, emoji = "ACCEPTABLE", "🟡"
        description = ("Acceptable quick calibration. Consider full "
                       "calibration for maximum accuracy.")
        if num_images < RECOMMENDED_IMAGES:
            recommendations.append(
                f"• Capture {RECOMMENDED_IMAGES - num_images} more images "
                "for better quality"
            )
    else:
        rating, emoji = "POOR", "🔴"
        description = "Poor calibration. Full calibration recommended."

    if rms_error < GOOD_RMS:
        recommendations.append("✓ Quick calibration successful")
        recommendations.append(
            "• For maximum accuracy, run Full Calibration mode"
        )
    else:
        recommendations.extend([
            "⚠️ High reprojection error detected",
            "• Try full calibration mode with 10+ images",
            "• Ensure board is perfectly flat and well-lit",
            "• Check camera focus is sharp",
        ])

    if num_images < RECOMMENDED_IMAGES:
        recommendations.append(
            f"• {RECOMMENDED_IMAGES} images recommended "
            f"(have {num_images})"
        )

    recommendations.extend([
        "Note: Quick mode uses simplified assumptions:",
        "  - Principal point fixed at image center",
        "  - Lens distortion not modeled",
    ])

    return {
        "rating": rating,
        "emoji": emoji,
        "description": description,
        "rms_error_px": float(rms_error),
        "num_images": num_images,
        "recommendations": recommendations,
    }
