"""Quick stereo calibration tool to update config values."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick stereo calibration to update config.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--left", type=Path, nargs="+", required=True, help="Left image paths.")
    parser.add_argument("--right", type=Path, nargs="+", required=True, help="Right image paths.")
    parser.add_argument("--pattern", default="9x6", help="Checkerboard pattern colsxrows.")
    parser.add_argument("--square-mm", type=float, required=True, help="Checkerboard square size in mm.")
    parser.add_argument("--write", action="store_true", help="Write calibration to config.")
    return parser.parse_args()


def _parse_pattern(pattern: str) -> Tuple[int, int]:
    cols, rows = pattern.lower().split("x")
    return int(cols), int(rows)


def _collect_corners(
    paths: List[Path],
    pattern_size: Tuple[int, int],
) -> Tuple[List[np.ndarray], List[np.ndarray], Tuple[int, int]]:
    objpoints: List[np.ndarray] = []
    imgpoints: List[np.ndarray] = []
    img_size: Tuple[int, int] | None = None

    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0 : pattern_size[0], 0 : pattern_size[1]].T.reshape(-1, 2)

    print(f"Processing {len(paths)} images for corner detection...")
    for i, path in enumerate(paths, 1):
        print(f"  [{i}/{len(paths)}] {path.name}...", end=" ", flush=True)
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            print("❌ Failed to load")
            continue
        img_size = (image.shape[1], image.shape[0])
        found, corners = cv2.findChessboardCorners(image, pattern_size)
        if not found:
            print("❌ No corners")
            continue
        corners = cv2.cornerSubPix(
            image,
            corners,
            winSize=(11, 11),
            zeroZone=(-1, -1),
            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
        )
        objpoints.append(objp.copy())
        imgpoints.append(corners)
        print("✓")

    print(f"Found corners in {len(objpoints)} images")
    if img_size is None:
        raise RuntimeError("No valid images found for calibration.")
    return objpoints, imgpoints, img_size


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
    """Calculate reprojection error for each calibration image pair.

    Returns:
        List of dicts with left_rms, right_rms, combined_rms for each image
    """
    errors = []
    rvec_zero = np.zeros(3)
    tvec_zero = np.zeros(3)

    for obj_pts, left_pts, right_pts in zip(objpoints, left_img, right_img):
        # Project to left camera
        left_projected, _ = cv2.projectPoints(
            obj_pts, rvec_zero, tvec_zero, mtx_left, dist_left
        )
        left_error = np.sqrt(np.mean((left_pts - left_projected.reshape(-1, 2)) ** 2))

        # Project to right camera (with rotation and translation)
        rvec_r, _ = cv2.Rodrigues(R)
        right_projected, _ = cv2.projectPoints(
            obj_pts, rvec_r, T, mtx_right, dist_right
        )
        right_error = np.sqrt(np.mean((right_pts - right_projected.reshape(-1, 2)) ** 2))

        combined_error = np.sqrt(left_error**2 + right_error**2)

        errors.append({
            "left_rms": float(left_error),
            "right_rms": float(right_error),
            "combined_rms": float(combined_error),
        })

    return errors


def _rate_calibration_quality(rms_error: float, num_images: int) -> dict:
    """Rate calibration quality and provide recommendations.

    Args:
        rms_error: Overall RMS reprojection error in pixels
        num_images: Number of image pairs used for calibration

    Returns:
        Dictionary with rating, description, and recommendations
    """
    # Quality thresholds
    EXCELLENT_RMS = 0.5
    GOOD_RMS = 1.0
    ACCEPTABLE_RMS = 2.0
    MIN_IMAGES_GOOD = 15
    MIN_IMAGES_ACCEPTABLE = 10

    recommendations = []

    # Determine rating
    if rms_error < EXCELLENT_RMS and num_images >= MIN_IMAGES_GOOD:
        rating = "EXCELLENT"
        emoji = "🟢"
        description = "Outstanding calibration! Ready for high-accuracy tracking."
    elif rms_error < GOOD_RMS and num_images >= MIN_IMAGES_GOOD:
        rating = "GOOD"
        emoji = "🟢"
        description = "Good calibration. Suitable for most tracking needs."
    elif rms_error < ACCEPTABLE_RMS and num_images >= MIN_IMAGES_ACCEPTABLE:
        rating = "ACCEPTABLE"
        emoji = "🟡"
        description = "Acceptable calibration. Consider recalibrating for better accuracy."
        recommendations.append("• Capture more images (aim for 15-20)")
        recommendations.append("• Cover full tracking volume with varied poses")
    else:
        rating = "POOR"
        emoji = "🔴"
        description = "Poor calibration. Please recalibrate for reliable tracking."

    # Add specific recommendations based on metrics
    if rms_error > 1.0:
        recommendations.extend([
            "• Hold checkerboard steadier during capture",
            "• Ensure checkerboard is perfectly flat",
            "• Check camera focus is sharp",
            "• Improve lighting (even, no shadows)",
        ])

    if num_images < MIN_IMAGES_ACCEPTABLE:
        recommendations.append(f"• Need at least {MIN_IMAGES_ACCEPTABLE} images (have {num_images})")
    elif num_images < MIN_IMAGES_GOOD:
        recommendations.append(f"• Capture {MIN_IMAGES_GOOD - num_images} more images for better quality")

    if rms_error > 2.0:
        recommendations.extend([
            "• Try recalibrating from scratch",
            "• Verify checkerboard dimensions are correct",
            "• Check for lens distortion or damage",
        ])

    return {
        "rating": rating,
        "emoji": emoji,
        "description": description,
        "rms_error_px": float(rms_error),
        "num_images": num_images,
        "recommendations": recommendations,
    }


def _calibrate(
    left_paths: List[Path],
    right_paths: List[Path],
    pattern_size: Tuple[int, int],
    square_mm: float,
) -> dict:
    print("\n=== LEFT CAMERA ===")
    left_obj, left_img, img_size = _collect_corners(left_paths, pattern_size)
    print("\n=== RIGHT CAMERA ===")
    right_obj, right_img, _ = _collect_corners(right_paths, pattern_size)

    if len(left_obj) != len(right_obj):
        raise RuntimeError("Left/right image counts do not match after corner detection.")
    if not left_obj:
        raise RuntimeError("No chessboard corners detected.")

    print(f"\nCalibrating with {len(left_obj)} image pairs...")
    objp = left_obj[0].copy()
    objp[:, :2] *= float(square_mm)
    objpoints = [objp for _ in left_obj]

    print("Calibrating left camera intrinsics...", flush=True)
    _, mtx_left, dist_left, _, _ = cv2.calibrateCamera(
        objpoints, left_img, img_size, None, None
    )
    print("✓ Left camera calibrated")

    print("Calibrating right camera intrinsics...", flush=True)
    _, mtx_right, dist_right, _, _ = cv2.calibrateCamera(
        objpoints, right_img, img_size, None, None
    )
    print("✓ Right camera calibrated")

    print("Computing stereo calibration...", flush=True)
    rms_error, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
        objpoints,
        left_img,
        right_img,
        mtx_left,
        dist_left,
        mtx_right,
        dist_right,
        img_size,
        flags=cv2.CALIB_FIX_INTRINSIC,
    )
    print(f"✓ Stereo calibration complete (RMS error: {rms_error:.3f} px)")

    baseline_mm = float(np.linalg.norm(T))
    baseline_ft = baseline_mm / 304.8
    focal_length_px = float(mtx_left[0, 0])
    cx = float(mtx_left[0, 2])
    cy = float(mtx_left[1, 2])

    # Compute per-image reprojection errors
    print("Computing per-image reprojection errors...", flush=True)
    per_image_errors = _compute_per_image_errors(
        objpoints, left_img, right_img,
        mtx_left, dist_left, mtx_right, dist_right,
        R, T
    )

    # Calculate quality rating
    num_images = len(objpoints)
    quality = _rate_calibration_quality(rms_error, num_images)

    # Print quality assessment
    print(f"\n{quality['emoji']} Calibration Quality: {quality['rating']}")
    print(f"   {quality['description']}")
    if quality['recommendations']:
        print("\nRecommendations:")
        for rec in quality['recommendations']:
            print(f"   {rec}")

    return {
        "baseline_ft": baseline_ft,
        "focal_length_px": focal_length_px,
        "cx": cx,
        "cy": cy,
        # Quality metrics
        "rms_error_px": float(rms_error),
        "num_images": num_images,
        "per_image_errors": per_image_errors,
        "quality": quality,
        # Include full calibration matrices for saving
        "mtx_left": mtx_left,
        "mtx_right": mtx_right,
        "dist_left": dist_left,
        "dist_right": dist_right,
        "R": R,
        "T": T,
        "E": E,
        "F": F,
        "img_size": img_size,
    }


def _write_config(config_path: Path, updates: dict) -> None:
    """Write scalar calibration values to YAML config.

    Only writes baseline_ft, focal_length_px, cx, cy to config.
    Full matrices are saved separately to npz file.
    """
    data = yaml.safe_load(config_path.read_text())
    data.setdefault("stereo", {})

    # Only write scalar values to YAML config (not numpy arrays)
    scalar_keys = ["baseline_ft", "focal_length_px", "cx", "cy"]
    for key in scalar_keys:
        if key in updates:
            data["stereo"][key] = updates[key]

    config_path.write_text(yaml.safe_dump(data, sort_keys=False))


def _save_calibration_file(updates: dict) -> None:
    """Save full calibration matrices and quality metrics to npz file."""
    calib_dir = Path("calibration")
    calib_dir.mkdir(parents=True, exist_ok=True)

    calib_path = calib_dir / "stereo_calibration.npz"

    # Extract quality info for saving
    quality = updates.get("quality", {})

    np.savez(
        calib_path,
        # Camera matrices
        mtx_left=updates["mtx_left"],
        mtx_right=updates["mtx_right"],
        dist_left=updates["dist_left"],
        dist_right=updates["dist_right"],
        R=updates["R"],
        T=updates["T"],
        img_size=updates["img_size"],
        # Stereo geometry
        baseline_ft=updates["baseline_ft"],
        focal_length_px=updates["focal_length_px"],
        cx=updates["cx"],
        cy=updates["cy"],
        # Quality metrics
        rms_error_px=updates.get("rms_error_px", 0.0),
        num_images=updates.get("num_images", 0),
        per_image_errors=updates.get("per_image_errors", []),
        quality_rating=quality.get("rating", "UNKNOWN"),
        quality_description=quality.get("description", ""),
    )


def load_calibration_quality(calib_path: Optional[Path] = None) -> Optional[dict]:
    """Load calibration quality metrics from saved calibration file.

    Args:
        calib_path: Path to calibration file (default: calibration/stereo_calibration.npz)

    Returns:
        Dict with quality metrics or None if file doesn't exist or has no quality data
    """
    if calib_path is None:
        calib_path = Path("calibration/stereo_calibration.npz")

    if not calib_path.exists():
        return None

    try:
        data = np.load(calib_path, allow_pickle=True)

        # Check if quality metrics exist (newer calibration files have them)
        if "quality_rating" not in data:
            return None

        return {
            "rms_error_px": float(data.get("rms_error_px", 0.0)),
            "num_images": int(data.get("num_images", 0)),
            "rating": str(data.get("quality_rating", "UNKNOWN")),
            "description": str(data.get("quality_description", "")),
        }
    except Exception:
        return None


def calibrate_and_write(
    left_paths: List[Path],
    right_paths: List[Path],
    pattern: str,
    square_mm: float,
    config_path: Path,
) -> dict:
    pattern_size = _parse_pattern(pattern)
    updates = _calibrate(left_paths, right_paths, pattern_size, square_mm)
    _write_config(config_path, updates)
    _save_calibration_file(updates)
    return updates


def main() -> None:
    args = parse_args()
    pattern = _parse_pattern(args.pattern)
    updates = _calibrate(args.left, args.right, pattern, args.square_mm)
    print("Calibration results:", updates)
    if args.write:
        _write_config(args.config, updates)
        print(f"Updated config: {args.config}")


if __name__ == "__main__":
    main()
