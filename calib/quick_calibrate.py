"""Quick stereo calibration tool — stable facade.

This module re-exports all public and internal symbols from the extracted
submodules so that every existing ``from calib.quick_calibrate import …``
continues to work unchanged.  New code should import from the focused
modules directly:

- ``calib.calibration_io``   — image loading, artifact persistence
- ``calib.stereo_matching``  — correspondence matching
- ``calib.calibration_quality`` — geometry validation, quality rating
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

# Re-export: data types
from calib.calibration_io import CornerDetection  # noqa: F401

# Re-export: image loading & artifact persistence
from calib.calibration_io import (  # noqa: F401
    _collect_corners,
    _save_calibration_file,
    _write_config,
    load_calibration_quality,
)

# Re-export: stereo pair matching
from calib.stereo_matching import (  # noqa: F401
    MIN_CHARUCO_STEREO_CORNERS,
    _match_stereo_pairs,
    _pair_diag,
)

# Re-export: geometry validation & quality assessment
from calib.calibration_quality import (  # noqa: F401
    MAX_STEREO_RMS_PX,
    MIN_BASELINE_FT,
    _compute_per_image_errors,
    _rate_calibration_quality,
    _rate_quick_calibration_quality,
    _validate_stereo_geometry,
)


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quick stereo calibration to update config."
    )
    parser.add_argument(
        "--config", type=Path, default=Path("configs/default.yaml"),
    )
    parser.add_argument(
        "--left", type=Path, nargs="+", required=True,
        help="Left image paths.",
    )
    parser.add_argument(
        "--right", type=Path, nargs="+", required=True,
        help="Right image paths.",
    )
    parser.add_argument(
        "--pattern", default="9x6",
        help="ChArUco board pattern colsxrows (number of squares).",
    )
    parser.add_argument(
        "--square-mm", type=float, required=True,
        help="ChArUco board square size in mm.",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Use quick calibration mode (3-5 images, simplified).",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Write calibration to config.",
    )
    return parser.parse_args()


def _parse_pattern(pattern: str) -> Tuple[int, int]:
    cols, rows = pattern.lower().split("x")
    return int(cols), int(rows)


# ---------------------------------------------------------------------------
# Quick calibration
# ---------------------------------------------------------------------------


def quick_calibrate(
    left_paths: List[Path],
    right_paths: List[Path],
    pattern_size: Tuple[int, int],
    square_mm: float,
) -> dict:
    """Quick calibration mode — minimal captures, simplified estimation.

    Raises:
        RuntimeError: If insufficient matching pairs found.
    """
    MIN_PAIRS = 3
    RECOMMENDED_PAIRS = 5

    print("\n=== QUICK CALIBRATION MODE ===")
    print(f"Target: {RECOMMENDED_PAIRS} image pairs (minimum: {MIN_PAIRS})")
    print("Using simplified parameter estimation for faster setup\n")

    print("=== LEFT CAMERA ===")
    left_dets, img_size = _collect_corners(left_paths, pattern_size, square_mm)
    print("\n=== RIGHT CAMERA ===")
    right_dets, _ = _collect_corners(right_paths, pattern_size, square_mm)

    print("\n=== MATCHING STEREO PAIRS ===")
    obj, l_img, r_img, rej, diag = _match_stereo_pairs(left_dets, right_dets)

    if rej:
        print("\nRejected images:")
        for msg in rej:
            print(f"  • {msg}")

    num = len(obj)
    print(f"\nMatched pairs: {num}/{len(left_paths)}")
    if num == 0:
        raise RuntimeError(
            "No matching image pairs found. Ensure ChArUco board is "
            "visible in BOTH cameras."
        )
    if num < MIN_PAIRS:
        raise RuntimeError(
            f"Insufficient pairs for quick calibration ({num} found, "
            f"need at least {MIN_PAIRS}). Capture more images with "
            "board visible in BOTH cameras."
        )
    if num < RECOMMENDED_PAIRS:
        print(f"⚠️  Only {num} pairs (recommended: {RECOMMENDED_PAIRS})")

    print(f"\nCalibrating with {num} pairs (QUICK mode)...")

    mtx_l, dist_l, mtx_r, dist_r = _quick_intrinsics(
        obj, l_img, r_img, img_size,
    )
    result = _stereo_solve_and_package(
        obj, l_img, r_img, mtx_l, dist_l, mtx_r, dist_r, img_size,
        left_paths, rej, diag, mode="QUICK",
    )
    return result


def _quick_intrinsics(
    objpoints: list, left_imgpoints: list, right_imgpoints: list,
    img_size: Tuple[int, int],
) -> tuple:
    """Estimate intrinsics with fixed principal point & zero distortion."""
    fx_init = 1200.0
    cx, cy = img_size[0] / 2.0, img_size[1] / 2.0
    mtx_left_init = np.array(
        [[fx_init, 0, cx], [0, fx_init, cy], [0, 0, 1]], dtype=np.float64,
    )
    calib_flags = (
        cv2.CALIB_USE_INTRINSIC_GUESS
        | cv2.CALIB_FIX_PRINCIPAL_POINT
        | cv2.CALIB_FIX_K1 | cv2.CALIB_FIX_K2 | cv2.CALIB_FIX_K3
        | cv2.CALIB_FIX_K4 | cv2.CALIB_FIX_K5 | cv2.CALIB_FIX_K6
        | cv2.CALIB_ZERO_TANGENT_DIST
    )

    print("Calibrating left camera (fixed principal point, zero "
          "distortion)...", flush=True)
    dist_l = np.zeros(5, dtype=np.float64)
    _, mtx_l, _, _, _ = cv2.calibrateCamera(
        objpoints, left_imgpoints, img_size,
        mtx_left_init, dist_l, flags=calib_flags,
    )
    print("✓ Left camera calibrated (quick mode)")

    print("Calibrating right camera (fixed principal point, zero "
          "distortion)...", flush=True)
    mtx_right_init = mtx_left_init.copy()
    dist_r = np.zeros(5, dtype=np.float64)
    _, mtx_r, _, _, _ = cv2.calibrateCamera(
        objpoints, right_imgpoints, img_size,
        mtx_right_init, dist_r, flags=calib_flags,
    )
    print("✓ Right camera calibrated (quick mode)")

    return mtx_l, dist_l, mtx_r, dist_r


# ---------------------------------------------------------------------------
# Full calibration
# ---------------------------------------------------------------------------


def _calibrate(
    left_paths: List[Path],
    right_paths: List[Path],
    pattern_size: Tuple[int, int],
    square_mm: float,
) -> dict:
    MIN_PAIRS = 10
    RECOMMENDED_PAIRS = 15

    print("\n=== LEFT CAMERA ===")
    left_dets, img_size = _collect_corners(left_paths, pattern_size, square_mm)
    print("\n=== RIGHT CAMERA ===")
    right_dets, _ = _collect_corners(right_paths, pattern_size, square_mm)

    print("\n=== MATCHING STEREO PAIRS ===")
    obj, l_img, r_img, rej, diag = _match_stereo_pairs(left_dets, right_dets)

    if rej:
        print("\nRejected images (corner detection failed in one or both "
              "cameras):")
        for msg in rej:
            print(f"  • {msg}")

    num = len(obj)
    print(f"\nMatched pairs: {num}/{len(left_paths)}")
    if num == 0:
        raise RuntimeError(
            "No matching image pairs found. Ensure calibration board "
            "(ChArUco or checkerboard) is visible in BOTH cameras for "
            "all images."
        )
    if num < MIN_PAIRS:
        raise RuntimeError(
            f"Insufficient matching pairs ({num} found, need at least "
            f"{MIN_PAIRS}). Recapture more images with calibration board "
            "visible in BOTH cameras."
        )
    if num < RECOMMENDED_PAIRS:
        print(f"⚠️  Warning: Only {num} pairs (recommended: "
              f"{RECOMMENDED_PAIRS}+)")

    print(f"\nCalibrating with {num} matched image pairs...")

    print("Calibrating left camera intrinsics...", flush=True)
    _, mtx_l, dist_l, _, _ = cv2.calibrateCamera(
        obj, l_img, img_size, None, None,
    )
    print("✓ Left camera calibrated")

    print("Calibrating right camera intrinsics...", flush=True)
    _, mtx_r, dist_r, _, _ = cv2.calibrateCamera(
        obj, r_img, img_size, None, None,
    )
    print("✓ Right camera calibrated")

    result = _stereo_solve_and_package(
        obj, l_img, r_img, mtx_l, dist_l, mtx_r, dist_r, img_size,
        left_paths, rej, diag, mode="FULL",
    )

    total_input = len(left_paths)
    rejected = total_input - num
    if rejected > 0:
        print("\n📊 Summary:")
        print(f"   Input images: {total_input} pairs")
        print(f"   Rejected: {rejected} pairs (corner detection failed)")
        print(f"   Used for calibration: {num} pairs ✓")

    return result


# ---------------------------------------------------------------------------
# Shared stereo solve + packaging
# ---------------------------------------------------------------------------


def _stereo_solve_and_package(
    objpoints: list, left_imgpoints: list, right_imgpoints: list,
    mtx_left: np.ndarray, dist_left: np.ndarray,
    mtx_right: np.ndarray, dist_right: np.ndarray,
    img_size: Tuple[int, int],
    left_paths: List[Path],
    rejection_report: list, pair_diagnostics: list,
    mode: str,
) -> dict:
    """Run stereo calibration, validate, rate quality, and package."""
    print("Computing stereo calibration...", flush=True)
    rms, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
        objpoints, left_imgpoints, right_imgpoints,
        mtx_left, dist_left, mtx_right, dist_right, img_size,
        flags=cv2.CALIB_FIX_INTRINSIC,
    )
    print(f"✓ Stereo calibration complete (RMS error: {rms:.3f} px)")

    baseline_mm = float(np.linalg.norm(T))
    baseline_ft = baseline_mm / 304.8
    num = len(objpoints)

    print("Computing per-image reprojection errors...", flush=True)
    per_img = _compute_per_image_errors(
        objpoints, left_imgpoints, right_imgpoints,
        mtx_left, dist_left, mtx_right, dist_right, R, T,
    )

    rate_fn = (_rate_quick_calibration_quality if mode == "QUICK"
               else _rate_calibration_quality)
    quality = rate_fn(rms, num)
    _validate_stereo_geometry(rms, baseline_ft, F)

    label = "Quick " if mode == "QUICK" else ""
    print(f"\n{quality['emoji']} {label}Calibration Quality: "
          f"{quality['rating']}")
    print(f"   {quality['description']}")
    if quality["recommendations"]:
        print("\nRecommendations:")
        for rec in quality["recommendations"]:
            print(f"   {rec}")

    return {
        "baseline_ft": baseline_ft,
        "focal_length_px": float(mtx_left[0, 0]),
        "cx": float(mtx_left[0, 2]),
        "cy": float(mtx_left[1, 2]),
        "rms_error_px": float(rms),
        "num_images": num,
        "num_images_used": num,
        "total_input_images": len(left_paths),
        "per_image_errors": per_img,
        "pair_diagnostics": pair_diagnostics,
        "rejection_report": rejection_report,
        "quality": quality,
        "quality_rating": quality["rating"],
        "quality_description": quality["description"],
        "quality_emoji": quality["emoji"],
        "recommendations": quality["recommendations"],
        "calibration_mode": mode,
        "mtx_left": mtx_left, "mtx_right": mtx_right,
        "dist_left": dist_left, "dist_right": dist_right,
        "R": R, "T": T, "E": E, "F": F,
        "img_size": img_size,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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

    if args.quick:
        print("Using QUICK calibration mode")
        updates = quick_calibrate(
            args.left, args.right, pattern, args.square_mm,
        )
    else:
        print("Using FULL calibration mode")
        updates = _calibrate(
            args.left, args.right, pattern, args.square_mm,
        )

    print("\nCalibration results:")
    print(f"  Mode: {updates.get('calibration_mode', 'FULL')}")
    print(f"  Baseline: {updates['baseline_ft']:.3f} ft")
    print(f"  Focal length: {updates['focal_length_px']:.1f} px")
    print(f"  RMS error: {updates['rms_error_px']:.3f} px")
    print(f"  Quality: {updates['quality_rating']}")

    if args.write:
        _write_config(args.config, updates)
        _save_calibration_file(updates)
        print(f"\n✓ Calibration saved to {args.config}")
        print("✓ Full matrices saved to calibration/stereo_calibration.npz")


if __name__ == "__main__":
    main()
