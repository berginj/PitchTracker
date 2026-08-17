"""Image analysis and reporting for the camera alignment CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

from exceptions import CalibrationExecutionError, CalibrationInputError


def validate_image_path(path: Path) -> Path:
    """Resolve and validate a local alignment image path."""
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise CalibrationInputError(f"Could not access image: {path}") from exc
    if not resolved.is_file():
        raise CalibrationInputError(f"Image path is not a file: {path}")
    return resolved


def load_frame(path: Path) -> np.ndarray:
    """Load frame from file."""
    resolved = validate_image_path(path)
    img = cv2.imread(str(resolved))
    if img is None:
        raise CalibrationInputError(f"Could not load image: {resolved}")
    return np.asarray(img)


def find_feature_matches(img1: np.ndarray, img2: np.ndarray, max_features: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
    """Find corresponding feature points between two images.

    Args:
        img1: First image (BGR or grayscale)
        img2: Second image (BGR or grayscale)
        max_features: Maximum number of features to detect

    Returns:
        Tuple of (points1, points2) as Nx2 arrays of matched coordinates
    """
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
    orb = getattr(cv2, "ORB_create")(nfeatures=max_features)

    # Detect keypoints and compute descriptors
    try:
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)
    except cv2.error as exc:
        raise CalibrationExecutionError("Feature detection failed") from exc

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        raise CalibrationInputError("Not enough features detected. Point cameras at textured scene (not blank wall).")

    # Match features using BFMatcher
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    if len(matches) < 20:
        raise CalibrationInputError(f"Not enough matches found ({len(matches)}). Need textured scene with detail.")

    # Sort by distance (quality)
    matches = sorted(matches, key=lambda x: x.distance)

    # Take best matches (top 50% or at least 50)
    num_good = max(50, len(matches) // 2)
    good_matches = matches[:num_good]

    # Extract matched point coordinates
    pts1 = np.asarray([kp1[m.queryIdx].pt for m in good_matches], dtype=np.float32)
    pts2 = np.asarray([kp2[m.trainIdx].pt for m in good_matches], dtype=np.float32)

    return pts1, pts2


def analyze_vertical_alignment(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze vertical alignment between cameras.

    Cameras should be at same height (y-coordinates should match).

    Args:
        pts1: Nx2 array of points from left camera
        pts2: Nx2 array of corresponding points from right camera

    Returns:
        Dict with vertical alignment metrics
    """
    # Calculate vertical disparity (difference in y-coordinates)
    y1 = pts1[:, 1]
    y2 = pts2[:, 1]
    vertical_disparity = y2 - y1

    # Statistics
    mean_v_disp = np.mean(vertical_disparity)
    std_v_disp = np.std(vertical_disparity)
    max_v_disp = np.max(np.abs(vertical_disparity))

    # Thresholds (empirical, for 720p resolution)
    EXCELLENT_THRESHOLD = 2.0  # pixels
    GOOD_THRESHOLD = 5.0
    ACCEPTABLE_THRESHOLD = 10.0

    if max_v_disp < EXCELLENT_THRESHOLD:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras are very well aligned vertically"
    elif max_v_disp < GOOD_THRESHOLD:
        status = "GOOD"
        severity = "ok"
        message = "Cameras are well aligned vertically"
    elif max_v_disp < ACCEPTABLE_THRESHOLD:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight vertical misalignment detected"
    else:
        status = "POOR"
        severity = "error"
        message = "Significant vertical misalignment - cameras at different heights"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_vertical_disparity_px": float(mean_v_disp),
        "std_vertical_disparity_px": float(std_v_disp),
        "max_vertical_disparity_px": float(max_v_disp),
        "recommendation": "Adjust camera heights to match" if severity == "error" else None,
    }


def analyze_horizontal_alignment(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze horizontal alignment (convergence/toe-in).

    For parallel cameras, horizontal disparity should be roughly constant
    across the image. Toe-in causes disparity to vary with position.

    Args:
        pts1: Nx2 array of points from left camera
        pts2: Nx2 array of corresponding points from right camera

    Returns:
        Dict with horizontal alignment metrics
    """
    # Calculate horizontal disparity
    x1 = pts1[:, 0]
    x2 = pts2[:, 0]
    horizontal_disparity = x1 - x2  # Left - right (positive = right camera sees it more to the right)

    # For parallel cameras, disparity should be roughly constant
    # Toe-in causes disparity to vary systematically with x position
    mean_h_disp = np.mean(horizontal_disparity)
    std_h_disp = np.std(horizontal_disparity)

    # Check for systematic variation (sign of toe-in)
    # Correlation between x-position and disparity
    correlation = np.corrcoef(x1, horizontal_disparity)[0, 1]

    # Thresholds
    STD_EXCELLENT = 5.0  # pixels
    STD_GOOD = 10.0
    STD_ACCEPTABLE = 20.0

    CORR_EXCELLENT = 0.1  # Low correlation = good
    CORR_ACCEPTABLE = 0.3

    # Determine status based on both metrics
    if std_h_disp < STD_EXCELLENT and abs(correlation) < CORR_EXCELLENT:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras are perfectly parallel (no convergence)"
    elif std_h_disp < STD_GOOD and abs(correlation) < CORR_ACCEPTABLE:
        status = "GOOD"
        severity = "ok"
        message = "Cameras are well aligned (minimal convergence)"
    elif std_h_disp < STD_ACCEPTABLE:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight convergence detected - cameras slightly angled"
    else:
        status = "POOR"
        severity = "error"
        if correlation > 0.3:
            message = "Cameras toed-IN (converging) - angled toward each other"
        elif correlation < -0.3:
            message = "Cameras toed-OUT (diverging) - angled away from each other"
        else:
            message = "Cameras not parallel - high disparity variation"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_horizontal_disparity_px": float(mean_h_disp),
        "std_horizontal_disparity_px": float(std_h_disp),
        "position_disparity_correlation": float(correlation),
        "recommendation": "Adjust camera angles to be parallel" if severity == "error" else None,
    }


def analyze_rotation(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze rotation difference between cameras.

    Detects if one camera is rolled/tilted relative to the other.

    Args:
        pts1: Nx2 array of points from left camera
        pts2: Nx2 array of corresponding points from right camera

    Returns:
        Dict with rotation metrics
    """
    # Estimate affine transformation between point sets
    # This includes rotation, scale, and translation
    try:
        # Need at least 3 points
        if len(pts1) < 3:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Not enough points to estimate rotation",
                "rotation_deg": 0.0,
            }

        # Use RANSAC to be robust to outliers
        M, mask = cv2.estimateAffinePartial2D(pts1, pts2, method=cv2.RANSAC, ransacReprojThreshold=5.0)

        if M is None:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Could not estimate rotation (no consistent transform found)",
                "rotation_deg": 0.0,
            }

        # Extract rotation angle from affine matrix
        # M = [cos(θ)  -sin(θ)  tx]
        #     [sin(θ)   cos(θ)  ty]
        rotation_rad = np.arctan2(M[1, 0], M[0, 0])
        rotation_deg = np.degrees(rotation_rad)

        # Thresholds
        EXCELLENT_THRESHOLD = 0.5  # degrees
        GOOD_THRESHOLD = 1.0
        ACCEPTABLE_THRESHOLD = 2.0

        abs_rotation = abs(rotation_deg)

        if abs_rotation < EXCELLENT_THRESHOLD:
            status = "EXCELLENT"
            severity = "ok"
            message = "No rotation difference detected"
        elif abs_rotation < GOOD_THRESHOLD:
            status = "GOOD"
            severity = "ok"
            message = "Minimal rotation difference"
        elif abs_rotation < ACCEPTABLE_THRESHOLD:
            status = "ACCEPTABLE"
            severity = "warning"
            message = f"Slight rotation detected ({rotation_deg:.1f}°)"
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
            "recommendation": "Adjust camera rotation to match" if severity == "error" else None,
        }

    except Exception as e:
        return {
            "status": "UNKNOWN",
            "severity": "warning",
            "message": f"Could not analyze rotation: {e}",
            "rotation_deg": 0.0,
        }


def print_alignment_report(vertical: dict, horizontal: dict, rotation: dict, num_features: int) -> bool:
    """Print formatted alignment report."""

    # Header
    print("\n" + "=" * 70)
    print("CAMERA ALIGNMENT REPORT")
    print("=" * 70)

    print(f"\nFeatures matched: {num_features}")

    # Vertical alignment
    print("\n--- VERTICAL ALIGNMENT (Height) ---")
    severity_symbol = {
        "ok": "[OK]",
        "warning": "[!]",
        "error": "[X]",
    }

    symbol = severity_symbol.get(vertical["severity"], "[?]")
    print(f"{symbol} Status: {vertical['status']}")
    print(f"    {vertical['message']}")
    print(f"    Mean vertical disparity: {vertical['mean_vertical_disparity_px']:.2f} px")
    print(f"    Max vertical disparity: {vertical['max_vertical_disparity_px']:.2f} px")
    if vertical["recommendation"]:
        print(f"    → {vertical['recommendation']}")

    # Horizontal alignment
    print("\n--- HORIZONTAL ALIGNMENT (Convergence) ---")
    symbol = severity_symbol.get(horizontal["severity"], "[?]")
    print(f"{symbol} Status: {horizontal['status']}")
    print(f"    {horizontal['message']}")
    print(f"    Disparity std dev: {horizontal['std_horizontal_disparity_px']:.2f} px")
    print(f"    Position correlation: {horizontal['position_disparity_correlation']:.3f}")
    if horizontal["recommendation"]:
        print(f"    → {horizontal['recommendation']}")

    # Rotation
    print("\n--- ROTATION ALIGNMENT (Roll) ---")
    symbol = severity_symbol.get(rotation["severity"], "[?]")
    print(f"{symbol} Status: {rotation['status']}")
    print(f"    {rotation['message']}")
    print(f"    Rotation difference: {rotation['rotation_deg']:.2f}°")
    if rotation.get("recommendation"):
        print(f"    → {rotation['recommendation']}")

    # Overall assessment
    print("\n--- OVERALL ASSESSMENT ---")

    all_severities = [vertical["severity"], horizontal["severity"], rotation["severity"]]

    if all(s == "ok" for s in all_severities):
        print("[OK] Cameras are well aligned!")
        print("     You can proceed with checkerboard calibration.")
        overall_pass = True
    elif any(s == "error" for s in all_severities):
        print("[X] Camera alignment issues detected!")
        print("    Fix the issues above before attempting calibration.")
        print("    High calibration errors (>5px) are expected with this alignment.")
        overall_pass = False
    else:
        print("[!] Camera alignment acceptable but not optimal.")
        print("    Consider improving alignment for best calibration results.")
        print("    Expected calibration error: 1-5 px")
        overall_pass = True

    print("=" * 70 + "\n")

    return overall_pass
