"""Automatic camera alignment check and correction for stereo calibration.

This module runs automatically during calibration setup to detect and correct
camera alignment issues (vertical offset, toe-in, rotation).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import yaml


@dataclass
class AlignmentResults:
    """Results from automatic camera alignment analysis."""

    # Raw measurements
    vertical_mean_px: float
    vertical_max_px: float
    convergence_std_px: float
    correlation: float
    rotation_deg: float
    num_matches: int
    scale_difference_percent: float  # NEW: Scale/focal length mismatch percentage

    # Quality assessment
    quality: str  # "EXCELLENT", "GOOD", "ACCEPTABLE", "POOR", "CRITICAL"
    vertical_status: str
    horizontal_status: str
    rotation_status: str
    scale_status: str  # NEW: Focal length/scale status

    # Automatic correction parameters
    rotation_correction_needed: bool
    rotation_left: float  # Degrees to rotate left image
    rotation_right: float  # Degrees to rotate right image
    vertical_offset_px: int  # Vertical shift for rectification

    # User-facing messages
    status_message: str
    warnings: list[str]
    corrections_applied: list[str]

    def can_calibrate(self) -> bool:
        """Check if calibration should be allowed with this alignment."""
        return self.quality != "CRITICAL"

    def should_warn_user(self) -> bool:
        """Check if user should be warned about alignment quality."""
        return self.quality in ["POOR", "CRITICAL"]


def analyze_alignment(left_img: np.ndarray, right_img: np.ndarray,
                      max_features: int = 1000) -> AlignmentResults:
    """Automatically analyze stereo camera alignment from frame pair.

    This function runs the complete alignment analysis and returns both
    measurements and automatic correction parameters.

    Args:
        left_img: Image from left camera (BGR or grayscale)
        right_img: Image from right camera (BGR or grayscale)
        max_features: Maximum number of features to detect

    Returns:
        AlignmentResults with measurements, quality assessment, and corrections
    """
    try:
        # Find feature matches
        pts1, pts2 = _find_feature_matches(left_img, right_img, max_features)
        num_matches = len(pts1)

        if num_matches < 50:
            return _insufficient_features_result(num_matches)

        # Analyze alignment dimensions
        vertical = _analyze_vertical(pts1, pts2)
        horizontal = _analyze_horizontal(pts1, pts2)
        rotation = _analyze_rotation(pts1, pts2)
        scale = _analyze_scale(pts1, pts2)  # NEW: Check focal length/scale mismatch

        # Extract key metrics
        vertical_mean = vertical["mean_vertical_disparity_px"]
        vertical_max = vertical["max_vertical_disparity_px"]
        convergence_std = horizontal["std_horizontal_disparity_px"]
        correlation = horizontal["position_disparity_correlation"]
        rotation_deg = rotation["rotation_deg"]
        scale_difference_percent = scale["scale_difference_percent"]  # NEW

        # Assess overall quality
        quality = _assess_quality(vertical_mean, convergence_std, rotation_deg, correlation, scale_difference_percent)

        # Determine automatic corrections
        rotation_correction_needed = abs(rotation_deg) > 1.0
        rotation_left = 0.0
        rotation_right = rotation_deg if rotation_correction_needed else 0.0
        vertical_offset_px = int(round(vertical_mean))

        # Build user messages
        status_message, warnings, corrections_applied = _build_messages(
            quality, vertical, horizontal, rotation, scale,  # Added scale
            rotation_correction_needed, rotation_deg, vertical_offset_px
        )

        return AlignmentResults(
            vertical_mean_px=vertical_mean,
            vertical_max_px=vertical_max,
            convergence_std_px=convergence_std,
            correlation=correlation,
            rotation_deg=rotation_deg,
            num_matches=num_matches,
            scale_difference_percent=scale_difference_percent,  # NEW
            quality=quality,
            vertical_status=vertical["status"],
            horizontal_status=horizontal["status"],
            rotation_status=rotation["status"],
            scale_status=scale["status"],  # NEW
            rotation_correction_needed=rotation_correction_needed,
            rotation_left=rotation_left,
            rotation_right=rotation_right,
            vertical_offset_px=vertical_offset_px,
            status_message=status_message,
            warnings=warnings,
            corrections_applied=corrections_applied
        )

    except Exception as e:
        # If anything fails, return error result
        return AlignmentResults(
            vertical_mean_px=0, vertical_max_px=0,
            convergence_std_px=0, correlation=0, rotation_deg=0, num_matches=0,
            scale_difference_percent=0.0,  # NEW
            quality="CRITICAL",
            vertical_status="UNKNOWN",
            horizontal_status="UNKNOWN",
            rotation_status="UNKNOWN",
            scale_status="UNKNOWN",  # NEW
            rotation_correction_needed=False,
            rotation_left=0, rotation_right=0, vertical_offset_px=0,
            status_message=f"Alignment check failed: {str(e)}",
            warnings=[f"Could not analyze alignment: {str(e)}"],
            corrections_applied=[]
        )


def apply_corrections(config_path: Path, results: AlignmentResults) -> None:
    """Automatically apply software corrections to configuration.

    Saves rotation and vertical offset corrections to config file.
    These are automatically applied during camera capture and calibration.

    Args:
        config_path: Path to configuration file (configs/default.yaml)
        results: Alignment analysis results with correction parameters
    """
    try:
        config_data = yaml.safe_load(config_path.read_text())

        # Apply rotation corrections
        if "camera" not in config_data:
            config_data["camera"] = {}

        config_data["camera"]["rotation_left"] = float(results.rotation_left)
        config_data["camera"]["rotation_right"] = float(results.rotation_right)
        config_data["camera"]["vertical_offset_px"] = int(results.vertical_offset_px)

        # Save alignment quality metrics for reference
        if "alignment_quality" not in config_data["camera"]:
            config_data["camera"]["alignment_quality"] = {}

        config_data["camera"]["alignment_quality"] = {
            "vertical_px": float(results.vertical_mean_px),
            "convergence_std": float(results.convergence_std_px),
            "rotation_deg": float(results.rotation_deg),
            "correlation": float(results.correlation),
            "quality": results.quality,
            "last_checked": datetime.now().isoformat(),
            "num_matches": results.num_matches
        }

        config_path.write_text(yaml.safe_dump(config_data))

    except Exception as e:
        raise RuntimeError(f"Failed to apply alignment corrections: {e}")


# ============================================================================
# Internal helper functions
# ============================================================================

def _find_feature_matches(img1: np.ndarray, img2: np.ndarray,
                         max_features: int) -> Tuple[np.ndarray, np.ndarray]:
    """Find corresponding feature points between two images."""
    # Convert to grayscale if needed
    if img1.ndim == 3:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    else:
        gray1 = img1

    if img2.ndim == 3:
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    else:
        gray2 = img2

    # Use ORB (fast, patent-free)
    orb = cv2.ORB_create(nfeatures=max_features)

    # Detect keypoints and compute descriptors
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        raise ValueError("Not enough features detected - point cameras at textured scene")

    # Match features
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    if len(matches) < 20:
        raise ValueError(f"Not enough matches found ({len(matches)}) - need textured scene")

    # Sort and take best matches
    matches = sorted(matches, key=lambda x: x.distance)
    num_good = max(50, len(matches) // 2)
    good_matches = matches[:num_good]

    # Extract coordinates
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])

    return pts1, pts2


def _analyze_vertical(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze vertical alignment (height difference)."""
    y1 = pts1[:, 1]
    y2 = pts2[:, 1]
    vertical_disparity = y2 - y1

    mean_v_disp = np.mean(vertical_disparity)
    std_v_disp = np.std(vertical_disparity)
    max_v_disp = np.max(np.abs(vertical_disparity))

    # Thresholds
    if max_v_disp < 2.0:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras well aligned vertically"
    elif max_v_disp < 5.0:
        status = "GOOD"
        severity = "ok"
        message = "Cameras well aligned vertically"
    elif max_v_disp < 10.0:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight vertical misalignment"
    else:
        status = "POOR"
        severity = "error"
        message = "Significant vertical misalignment"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_vertical_disparity_px": float(mean_v_disp),
        "std_vertical_disparity_px": float(std_v_disp),
        "max_vertical_disparity_px": float(max_v_disp),
    }


def _analyze_horizontal(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze horizontal alignment (toe-in/convergence)."""
    x1 = pts1[:, 0]
    x2 = pts2[:, 0]
    horizontal_disparity = x1 - x2

    mean_h_disp = np.mean(horizontal_disparity)
    std_h_disp = np.std(horizontal_disparity)
    correlation = np.corrcoef(x1, horizontal_disparity)[0, 1]

    # Thresholds
    if std_h_disp < 5.0 and abs(correlation) < 0.1:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras perfectly parallel"
    elif std_h_disp < 10.0 and abs(correlation) < 0.3:
        status = "GOOD"
        severity = "ok"
        message = "Cameras well aligned (minimal convergence)"
    elif std_h_disp < 20.0:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight convergence detected"
    else:
        status = "POOR"
        severity = "error"
        if correlation > 0.3:
            message = "Cameras toed-IN (converging)"
        elif correlation < -0.3:
            message = "Cameras toed-OUT (diverging)"
        else:
            message = "Cameras not parallel"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_horizontal_disparity_px": float(mean_h_disp),
        "std_horizontal_disparity_px": float(std_h_disp),
        "position_disparity_correlation": float(correlation),
    }


def _analyze_rotation(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze rotation difference (roll/tilt)."""
    try:
        if len(pts1) < 3:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Not enough points for rotation estimate",
                "rotation_deg": 0.0,
            }

        # Estimate affine transform with RANSAC
        M, mask = cv2.estimateAffinePartial2D(pts1, pts2, method=cv2.RANSAC,
                                              ransacReprojThreshold=5.0)

        if M is None:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Could not estimate rotation",
                "rotation_deg": 0.0,
            }

        # Extract rotation angle
        rotation_rad = np.arctan2(M[1, 0], M[0, 0])
        rotation_deg = np.degrees(rotation_rad)

        # Thresholds
        abs_rotation = abs(rotation_deg)
        if abs_rotation < 0.5:
            status = "EXCELLENT"
            severity = "ok"
            message = "No rotation difference"
        elif abs_rotation < 1.0:
            status = "GOOD"
            severity = "ok"
            message = "Minimal rotation difference"
        elif abs_rotation < 2.0:
            status = "ACCEPTABLE"
            severity = "warning"
            message = f"Slight rotation ({rotation_deg:.1f}°)"
        else:
            status = "POOR"
            severity = "error"
            direction = "clockwise" if rotation_deg > 0 else "counter-clockwise"
            message = f"Significant rotation ({rotation_deg:.1f}° {direction})"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "rotation_deg": float(rotation_deg),
        }

    except Exception:
        return {
            "status": "UNKNOWN",
            "severity": "warning",
            "message": "Rotation analysis failed",
            "rotation_deg": 0.0,
        }


def _analyze_scale(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze scale difference (focal length mismatch).

    If cameras have different focal lengths (one zoomed in more),
    the same features will appear at different scales.
    """
    try:
        if len(pts1) < 10:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Not enough points for scale estimate",
                "scale_difference_percent": 0.0,
            }

        # Compute pairwise distances between features in each image
        # If scales match, distance ratios should be ~1.0

        # Sample random pairs to estimate scale
        np.random.seed(42)  # Reproducible
        n_samples = min(50, len(pts1))
        indices = np.random.choice(len(pts1), size=n_samples, replace=False)

        scale_ratios = []
        for i in range(len(indices) - 1):
            idx1 = indices[i]
            idx2 = indices[i + 1]

            # Distance in left image
            dist1 = np.linalg.norm(pts1[idx1] - pts1[idx2])
            # Distance in right image
            dist2 = np.linalg.norm(pts2[idx1] - pts2[idx2])

            if dist2 > 1.0:  # Avoid division by very small numbers
                scale_ratios.append(dist1 / dist2)

        if len(scale_ratios) < 5:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Insufficient data for scale estimate",
                "scale_difference_percent": 0.0,
            }

        # Median scale ratio (robust to outliers)
        median_scale = np.median(scale_ratios)

        # Scale difference as percentage
        # 1.0 = perfect match, 1.1 = 10% larger in left camera
        scale_difference_percent = abs(median_scale - 1.0) * 100

        # Thresholds
        if scale_difference_percent < 2.0:
            status = "EXCELLENT"
            severity = "ok"
            message = "Focal lengths match well"
        elif scale_difference_percent < 5.0:
            status = "GOOD"
            severity = "ok"
            message = "Focal lengths nearly match"
        elif scale_difference_percent < 10.0:
            status = "ACCEPTABLE"
            severity = "warning"
            message = f"Slight focal length mismatch ({scale_difference_percent:.1f}%)"
        else:
            status = "POOR"
            severity = "error"
            which_larger = "left" if median_scale > 1.0 else "right"
            message = f"Focal length mismatch ({scale_difference_percent:.1f}% - {which_larger} camera more zoomed)"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "scale_difference_percent": float(scale_difference_percent),
            "scale_ratio": float(median_scale),
        }

    except Exception:
        return {
            "status": "UNKNOWN",
            "severity": "warning",
            "message": "Scale analysis failed",
            "scale_difference_percent": 0.0,
        }


def _assess_quality(vertical_px: float, convergence_std: float,
                   rotation_deg: float, correlation: float, scale_difference_percent: float) -> str:
    """Assess overall alignment quality."""
    # Critical - block calibration
    if correlation < 0.3 or convergence_std > 40 or scale_difference_percent > 15:
        return "CRITICAL"

    # Poor - strong warning
    if vertical_px > 20 or convergence_std > 20 or abs(rotation_deg) > 5 or scale_difference_percent > 10:
        return "POOR"

    # Acceptable - minor warning
    if vertical_px > 10 or convergence_std > 10 or abs(rotation_deg) > 3 or scale_difference_percent > 5:
        return "ACCEPTABLE"

    # Good
    if vertical_px > 5 or convergence_std > 5 or abs(rotation_deg) > 1 or scale_difference_percent > 2:
        return "GOOD"

    # Excellent
    return "EXCELLENT"


def _build_messages(quality: str, vertical: dict, horizontal: dict, rotation: dict, scale: dict,
                   rotation_correction_needed: bool, rotation_deg: float,
                   vertical_offset_px: int) -> Tuple[str, list[str], list[str]]:
    """Build user-facing status messages."""
    warnings = []
    corrections_applied = []

    if quality == "CRITICAL":
        status_message = "Camera alignment is too poor for calibration"
        if horizontal["severity"] == "error":
            warnings.append("Severe toe-in detected - cameras must be adjusted to be parallel")
        if scale["severity"] == "error":
            warnings.append(f"Focal length mismatch detected - {scale['message']}")
            warnings.append("Adjust camera focus rings to match or check manual focus settings")
        warnings.append("Physical adjustment required before calibration")
    elif quality == "POOR":
        status_message = "Camera alignment is poor - calibration will have reduced accuracy"
        if horizontal["severity"] == "error":
            warnings.append(f"{horizontal['message']} - consider adjusting camera angles")
        if vertical["severity"] == "error":
            warnings.append(f"{vertical['message']} - consider adjusting camera heights")
        if rotation["severity"] == "error" and not rotation_correction_needed:
            warnings.append(f"{rotation['message']} - consider leveling cameras")
        if scale["severity"] == "error":
            warnings.append(f"{scale['message']} - adjust camera focus settings")
    elif quality == "ACCEPTABLE":
        status_message = "Camera alignment is acceptable with software corrections"
        if horizontal["severity"] == "warning":
            warnings.append(f"{horizontal['message']}")
        if scale["severity"] == "warning":
            warnings.append(f"{scale['message']} - check camera focus")
    elif quality == "GOOD":
        status_message = "Camera alignment is good"
    else:
        status_message = "Camera alignment is excellent"

    # Corrections applied
    if rotation_correction_needed:
        corrections_applied.append(f"Rotation correction applied ({rotation_deg:.1f}° → 0°)")

    if abs(vertical_offset_px) > 5:
        corrections_applied.append(f"Vertical offset correction saved ({vertical_offset_px} px)")

    return status_message, warnings, corrections_applied


def _insufficient_features_result(num_matches: int) -> AlignmentResults:
    """Return result when insufficient features are detected."""
    return AlignmentResults(
        vertical_mean_px=0, vertical_max_px=0,
        convergence_std_px=0, correlation=0, rotation_deg=0,
        num_matches=num_matches,
        scale_difference_percent=0.0,  # NEW
        quality="CRITICAL",
        vertical_status="UNKNOWN",
        horizontal_status="UNKNOWN",
        rotation_status="UNKNOWN",
        scale_status="UNKNOWN",  # NEW
        rotation_correction_needed=False,
        rotation_left=0, rotation_right=0, vertical_offset_px=0,
        status_message="Not enough features detected",
        warnings=[
            f"Only {num_matches} features matched (need 50+)",
            "Point cameras at textured scene (posters, books, NOT blank wall)",
            "Ensure good lighting and both cameras see common objects"
        ],
        corrections_applied=[]
    )
