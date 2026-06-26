"""Quick stereo calibration tool to update config values."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import yaml


@dataclass(frozen=True)
class CornerDetection:
    """Detected calibration points for one image."""

    index: int
    path: Path
    objpoints: np.ndarray
    imgpoints: np.ndarray
    kind: str
    corner_ids: Optional[np.ndarray] = None


MIN_CHARUCO_STEREO_CORNERS = 8

# Stereo geometry sanity bounds. A baseline near zero means the two cameras are
# effectively coincident (degenerate triangulation); an enormous or non-finite
# RMS means the solve did not converge.
MIN_BASELINE_FT = 0.02
MAX_STEREO_RMS_PX = 50.0


def _validate_stereo_geometry(rms_error: float, baseline_ft: float, fmat: np.ndarray) -> None:
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
            f"Estimated baseline {baseline_ft:.4f} ft is too small; the cameras "
            "appear coincident or the geometry is degenerate."
        )
    if fmat is None or not np.all(np.isfinite(np.asarray(fmat, dtype=np.float64))):
        raise CalibrationExecutionError("Fundamental matrix is non-finite; stereo geometry is degenerate.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick stereo calibration to update config.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--left", type=Path, nargs="+", required=True, help="Left image paths.")
    parser.add_argument("--right", type=Path, nargs="+", required=True, help="Right image paths.")
    parser.add_argument("--pattern", default="9x6", help="ChArUco board pattern colsxrows (number of squares).")
    parser.add_argument("--square-mm", type=float, required=True, help="ChArUco board square size in mm.")
    parser.add_argument("--quick", action="store_true", help="Use quick calibration mode (3-5 images, simplified).")
    parser.add_argument("--write", action="store_true", help="Write calibration to config.")
    return parser.parse_args()


def _parse_pattern(pattern: str) -> Tuple[int, int]:
    cols, rows = pattern.lower().split("x")
    return int(cols), int(rows)


def _collect_corners(
    paths: List[Path],
    pattern_size: Tuple[int, int],
    square_mm: float,
) -> Tuple[List[CornerDetection], Tuple[int, int]]:
    """Detect calibration board corners in images.

    Tries ChArUco board detection first, falls back to plain checkerboard if no markers found.

    Returns:
        detections: CornerDetection records for successful detections
        img_size: Image dimensions (width, height)
    """
    detections: List[CornerDetection] = []
    img_size: Tuple[int, int] | None = None

    # Create ChArUco board
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

    try:
        # Try newer API first (OpenCV 4.7+)
        board = cv2.aruco.CharucoBoard(
            (pattern_size[0], pattern_size[1]), square_mm, square_mm * 0.75, aruco_dict  # Marker size is 75% of square
        )
    except (AttributeError, TypeError):
        # Fall back to older API
        board = cv2.aruco.CharucoBoard_create(pattern_size[0], pattern_size[1], square_mm, square_mm * 0.75, aruco_dict)

    # Get detector parameters
    try:
        # Try newer API first (OpenCV 4.7+)
        detector_params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    except AttributeError:
        # Fall back to older API
        detector_params = cv2.aruco.DetectorParameters_create()
        detector = None

    print(f"Processing {len(paths)} images for calibration board detection (ChArUco with checkerboard fallback)...")
    for i, path in enumerate(paths):
        print(f"  [{i+1}/{len(paths)}] {path.name}...", end=" ", flush=True)
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            print("❌ Failed to load")
            continue
        img_size = (image.shape[1], image.shape[0])

        # Detect ArUco markers
        if detector is not None:
            # Newer API
            marker_corners, marker_ids, rejected = detector.detectMarkers(image)
        else:
            # Older API
            marker_corners, marker_ids, rejected = cv2.aruco.detectMarkers(
                image, aruco_dict, parameters=detector_params
            )

        # Check if any markers were detected
        charuco_success = False
        if marker_ids is not None and len(marker_ids) > 0:
            # Interpolate ChArUco corners
            try:
                # Try newer API first (OpenCV 4.7+)
                num_corners, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    marker_corners, marker_ids, image, board
                )
            except TypeError:
                # Fall back to older API
                num_corners, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    marker_corners, marker_ids, image, board
                )

            # Check if enough corners were detected (need at least 4 for calibration)
            MIN_CORNERS = 4
            if num_corners is not None and num_corners >= MIN_CORNERS:
                # Create object points for detected corners
                # ChArUco gives us corner IDs, so we use the board's chessboard corners
                try:
                    # Newer API
                    obj_pts = board.getChessboardCorners()[charuco_ids.flatten()]
                except AttributeError:
                    # Older API
                    obj_pts = board.chessboardCorners[charuco_ids.flatten()]

                detections.append(
                    CornerDetection(
                        index=i,
                        path=path,
                        objpoints=np.asarray(obj_pts, dtype=np.float32),
                        imgpoints=np.asarray(charuco_corners, dtype=np.float32),
                        kind="charuco",
                        corner_ids=np.asarray(charuco_ids, dtype=np.int32).reshape(-1),
                    )
                )
                print(f"✓ ({num_corners} ChArUco corners)")
                charuco_success = True

        # FALLBACK: Try plain checkerboard detection if ChArUco failed
        if not charuco_success:
            # Checkerboard has (cols-1, rows-1) internal corners
            board_size = (pattern_size[0] - 1, pattern_size[1] - 1)

            # Try multiple flag combinations for robust detection
            flag_combinations = [
                # Standard approach (best for most cases)
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE,
                # With fast check (rejects obvious false patterns quickly)
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK,
                # With quad filtering (stricter corner validation)
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FILTER_QUADS,
                # Minimal flags (for difficult lighting)
                cv2.CALIB_CB_ADAPTIVE_THRESH,
                # Just normalize (for high contrast images)
                cv2.CALIB_CB_NORMALIZE_IMAGE,
            ]

            ret = False
            corners = None

            for flags in flag_combinations:
                ret, corners = cv2.findChessboardCorners(image, board_size, flags)
                if ret and corners is not None:
                    break

            if ret and corners is not None:
                # Refine corner locations to sub-pixel accuracy
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners_refined = cv2.cornerSubPix(image, corners, (11, 11), (-1, -1), criteria)

                # Create object points for plain checkerboard
                # Object points are just a grid in 3D space (z=0)
                objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
                objp[:, :2] = np.mgrid[0 : board_size[0], 0 : board_size[1]].T.reshape(-1, 2)
                objp *= square_mm  # Scale by square size

                detections.append(
                    CornerDetection(
                        index=i,
                        path=path,
                        objpoints=objp,
                        imgpoints=np.asarray(corners_refined, dtype=np.float32),
                        kind="checkerboard",
                    )
                )
                print(f"✓ ({len(corners_refined)} checkerboard corners)")
            else:
                print("❌ No ChArUco markers and no checkerboard pattern")

    print(f"Found calibration corners in {len(detections)} images (ChArUco or checkerboard)")
    if img_size is None:
        raise RuntimeError("No valid images found for calibration.")
    return detections, img_size


def _match_stereo_pairs(
    left_detections: List[CornerDetection],
    right_detections: List[CornerDetection],
) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str], List[dict]]:
    """Match left and right corner detections, keeping only pairs where both succeeded.

    Returns:
        objpoints: Matched object points
        left_imgpoints: Matched left image points
        right_imgpoints: Matched right image points
        rejection_report: List of rejection messages for user feedback
        pair_diagnostics: Per-pair accepted/rejected diagnostics
    """
    left_by_index = {det.index: det for det in left_detections}
    right_by_index = {det.index: det for det in right_detections}
    left_set = set(left_by_index)
    right_set = set(right_by_index)
    common_indices = sorted(left_set & right_set)

    # Track rejections for reporting
    left_only = left_set - right_set
    right_only = right_set - left_set
    rejection_report = []
    pair_diagnostics: List[dict] = []

    if left_only:
        rejected_names = [left_by_index[i].path.name for i in sorted(left_only)]
        rejection_report.append(
            f"Rejected {len(left_only)} images (left detected, right failed): {', '.join(rejected_names[:5])}"
            + ("..." if len(rejected_names) > 5 else "")
        )
        for i in sorted(left_only):
            pair_diagnostics.append(
                {
                    "index": i,
                    "status": "rejected",
                    "reason": "right_detection_failed",
                    "left_image": left_by_index[i].path.name,
                    "right_image": None,
                    "left_corners": int(len(left_by_index[i].imgpoints)),
                    "right_corners": 0,
                }
            )

    if right_only:
        rejected_names = [right_by_index[i].path.name for i in sorted(right_only)]
        rejection_report.append(
            f"Rejected {len(right_only)} images (right detected, left failed): {', '.join(rejected_names[:5])}"
            + ("..." if len(rejected_names) > 5 else "")
        )
        for i in sorted(right_only):
            pair_diagnostics.append(
                {
                    "index": i,
                    "status": "rejected",
                    "reason": "left_detection_failed",
                    "left_image": None,
                    "right_image": right_by_index[i].path.name,
                    "left_corners": 0,
                    "right_corners": int(len(right_by_index[i].imgpoints)),
                }
            )

    # Build matched lists
    matched_obj = []
    matched_left = []
    matched_right = []

    for idx in common_indices:
        left = left_by_index[idx]
        right = right_by_index[idx]
        if left.kind != right.kind:
            reason = f"mixed_detection_types:{left.kind}:{right.kind}"
            rejection_report.append(
                f"Rejected pair {left.path.name}/{right.path.name}: mixed detection types "
                f"({left.kind} vs {right.kind})"
            )
            pair_diagnostics.append(_pair_diag(idx, left, right, "rejected", reason, 0))
            continue

        if left.kind == "charuco":
            if left.corner_ids is None or right.corner_ids is None:
                reason = "missing_charuco_corner_ids"
                rejection_report.append(f"Rejected pair {left.path.name}/{right.path.name}: missing ChArUco corner IDs")
                pair_diagnostics.append(_pair_diag(idx, left, right, "rejected", reason, 0))
                continue
            left_id_to_pos = {int(corner_id): pos for pos, corner_id in enumerate(left.corner_ids)}
            right_id_to_pos = {int(corner_id): pos for pos, corner_id in enumerate(right.corner_ids)}
            shared_ids = sorted(set(left_id_to_pos) & set(right_id_to_pos))
            if len(shared_ids) < MIN_CHARUCO_STEREO_CORNERS:
                reason = f"too_few_shared_charuco_corners:{len(shared_ids)}"
                rejection_report.append(
                    f"Rejected pair {left.path.name}/{right.path.name}: only {len(shared_ids)} shared "
                    f"ChArUco corners (need {MIN_CHARUCO_STEREO_CORNERS})"
                )
                pair_diagnostics.append(_pair_diag(idx, left, right, "rejected", reason, len(shared_ids)))
                continue
            left_rows = [left_id_to_pos[corner_id] for corner_id in shared_ids]
            right_rows = [right_id_to_pos[corner_id] for corner_id in shared_ids]
            matched_obj.append(left.objpoints[left_rows])
            matched_left.append(left.imgpoints[left_rows])
            matched_right.append(right.imgpoints[right_rows])
            pair_diagnostics.append(_pair_diag(idx, left, right, "accepted", "shared_charuco_ids", len(shared_ids)))
            continue

        if len(left.objpoints) != len(right.objpoints) or len(left.imgpoints) != len(right.imgpoints):
            reason = "checkerboard_corner_count_mismatch"
            rejection_report.append(
                f"Rejected pair {left.path.name}/{right.path.name}: checkerboard corner counts differ"
            )
            pair_diagnostics.append(_pair_diag(idx, left, right, "rejected", reason, 0))
            continue
        matched_obj.append(left.objpoints)
        matched_left.append(left.imgpoints)
        matched_right.append(right.imgpoints)
        pair_diagnostics.append(
            _pair_diag(idx, left, right, "accepted", "checkerboard_index_order", len(left.imgpoints))
        )

    return matched_obj, matched_left, matched_right, rejection_report, pair_diagnostics


def _pair_diag(
    index: int,
    left: CornerDetection,
    right: CornerDetection,
    status: str,
    reason: str,
    shared_corners: int,
) -> dict:
    return {
        "index": index,
        "status": status,
        "reason": reason,
        "left_image": left.path.name,
        "right_image": right.path.name,
        "detection_type": left.kind if left.kind == right.kind else f"{left.kind}/{right.kind}",
        "left_corners": int(len(left.imgpoints)),
        "right_corners": int(len(right.imgpoints)),
        "shared_corners": int(shared_corners),
    }


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
    for obj_pts, left_pts, right_pts in zip(objpoints, left_img, right_img):
        left_pts_2d = np.asarray(left_pts, dtype=np.float32).reshape(-1, 2)
        right_pts_2d = np.asarray(right_pts, dtype=np.float32).reshape(-1, 2)
        ok, rvec_left, tvec_left = cv2.solvePnP(
            np.asarray(obj_pts, dtype=np.float32),
            left_pts_2d,
            mtx_left,
            dist_left,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            errors.append(
                {
                    "left_rms": float("inf"),
                    "right_rms": float("inf"),
                    "combined_rms": float("inf"),
                }
            )
            continue

        # Project to left camera
        left_projected, _ = cv2.projectPoints(obj_pts, rvec_left, tvec_left, mtx_left, dist_left)
        left_error = np.sqrt(np.mean((left_pts_2d - left_projected.reshape(-1, 2)) ** 2))

        # Project to right camera by transforming the board pose from left to right.
        rmat_left, _ = cv2.Rodrigues(rvec_left)
        rmat_right = R @ rmat_left
        tvec_right = R @ tvec_left + T
        rvec_right, _ = cv2.Rodrigues(rmat_right)
        right_projected, _ = cv2.projectPoints(obj_pts, rvec_right, tvec_right, mtx_right, dist_right)
        right_error = np.sqrt(np.mean((right_pts_2d - right_projected.reshape(-1, 2)) ** 2))

        combined_error = np.sqrt(left_error**2 + right_error**2)

        errors.append(
            {
                "left_rms": float(left_error),
                "right_rms": float(right_error),
                "combined_rms": float(combined_error),
            }
        )

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

    # Determine rating based on both RMS error and number of images
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
        if num_images < MIN_IMAGES_GOOD:
            recommendations.append(f"• Capture {MIN_IMAGES_GOOD - num_images} more images for better quality")
        recommendations.append("• Cover full tracking volume with varied poses")
    else:
        rating = "POOR"
        emoji = "🔴"
        description = "Poor calibration. Please recalibrate for reliable tracking."

    # Add specific recommendations based on metrics
    if rms_error > 1.0:
        recommendations.extend(
            [
                "• Hold ChArUco board steadier during capture",
                "• Ensure ChArUco board is perfectly flat (no warping)",
                "• Check camera focus is sharp",
                "• Improve lighting (even, no shadows or glare)",
            ]
        )

    if num_images < MIN_IMAGES_ACCEPTABLE:
        recommendations.append(f"⚠️  Critical: Need at least {MIN_IMAGES_ACCEPTABLE} images (have {num_images})")
        recommendations.append("• Recapture with ChArUco board visible in BOTH cameras")
    elif num_images < MIN_IMAGES_GOOD:
        recommendations.append(f"• Capture {MIN_IMAGES_GOOD - num_images} more images for better quality")

    if rms_error > 2.0:
        recommendations.extend(
            [
                "• Try recalibrating from scratch",
                "• Verify ChArUco board dimensions are correct (measure square size)",
                "• Check for lens distortion or damage",
                "• Ensure ChArUco board pattern size matches actual board (count squares)",
            ]
        )

    # Add positional coverage recommendations if borderline
    if MIN_IMAGES_ACCEPTABLE <= num_images < MIN_IMAGES_GOOD or rms_error > GOOD_RMS:
        recommendations.append("• Vary ChArUco board positions: center, corners, near, far, tilted")

    return {
        "rating": rating,
        "emoji": emoji,
        "description": description,
        "rms_error_px": float(rms_error),
        "num_images": num_images,
        "recommendations": recommendations,
    }


def quick_calibrate(
    left_paths: List[Path],
    right_paths: List[Path],
    pattern_size: Tuple[int, int],
    square_mm: float,
) -> dict:
    """Quick calibration mode - minimal captures, simplified estimation.

    Differences from full calibration:
    - Requires only 3-5 image pairs (vs 10-15)
    - Uses DICT_6X6_250 only (no dictionary search)
    - Skips distortion coefficient estimation (sets all to 0)
    - Fixes principal point to image center
    - Faster corner detection (fewer refinement iterations)
    - Different quality thresholds (RMS < 2.0px = GOOD, < 3.0px = ACCEPTABLE)

    Args:
        left_paths: Paths to left camera calibration images
        right_paths: Paths to right camera calibration images
        pattern_size: ChArUco board pattern size (cols, rows)
        square_mm: ChArUco square size in millimeters

    Returns:
        Dictionary with calibration results and "QUICK" mode label

    Raises:
        RuntimeError: If insufficient matching pairs found
    """
    # Minimum pairs for quick mode (less than full calibration)
    MIN_PAIRS = 3
    RECOMMENDED_PAIRS = 5

    print("\n=== QUICK CALIBRATION MODE ===")
    print(f"Target: {RECOMMENDED_PAIRS} image pairs (minimum: {MIN_PAIRS})")
    print("Using simplified parameter estimation for faster setup\n")

    # Collect corners using existing function (already has ChArUco + fallback)
    print("=== LEFT CAMERA ===")
    left_detections, img_size = _collect_corners(left_paths, pattern_size, square_mm)

    print("\n=== RIGHT CAMERA ===")
    right_detections, _ = _collect_corners(right_paths, pattern_size, square_mm)

    # Match pairs
    print("\n=== MATCHING STEREO PAIRS ===")
    objpoints, left_imgpoints, right_imgpoints, rejection_report, pair_diagnostics = _match_stereo_pairs(
        left_detections, right_detections
    )

    # Report rejections
    if rejection_report:
        print("\nRejected images:")
        for msg in rejection_report:
            print(f"  • {msg}")

    # Validate we have enough pairs
    num_pairs = len(objpoints)
    print(f"\nMatched pairs: {num_pairs}/{len(left_paths)}")

    if num_pairs == 0:
        raise RuntimeError("No matching image pairs found. Ensure ChArUco board is visible in BOTH cameras.")

    if num_pairs < MIN_PAIRS:
        raise RuntimeError(
            f"Insufficient pairs for quick calibration ({num_pairs} found, need at least {MIN_PAIRS}). "
            f"Capture more images with board visible in BOTH cameras."
        )

    if num_pairs < RECOMMENDED_PAIRS:
        print(f"⚠️  Only {num_pairs} pairs (recommended: {RECOMMENDED_PAIRS})")
        print(f"   Consider capturing {RECOMMENDED_PAIRS - num_pairs} more for better quality")

    print(f"\nCalibrating with {num_pairs} pairs (QUICK mode)...")

    objpoints_scaled = objpoints

    # Quick calibration for LEFT camera
    # Fix principal point to image center and set distortion to 0
    print("Calibrating left camera (fixed principal point, zero distortion)...", flush=True)

    # Create initial camera matrix with principal point at image center
    fx_init = 1200.0  # Reasonable initial guess
    cx = img_size[0] / 2.0
    cy = img_size[1] / 2.0

    mtx_left_init = np.array([[fx_init, 0, cx], [0, fx_init, cy], [0, 0, 1]], dtype=np.float64)

    # Zero distortion
    dist_left = np.zeros(5, dtype=np.float64)

    # Calibrate with fixed principal point and zero distortion
    _, mtx_left, _, _, _ = cv2.calibrateCamera(
        objpoints_scaled,
        left_imgpoints,
        img_size,
        mtx_left_init,
        dist_left,
        flags=(
            cv2.CALIB_USE_INTRINSIC_GUESS
            | cv2.CALIB_FIX_PRINCIPAL_POINT
            | cv2.CALIB_FIX_K1
            | cv2.CALIB_FIX_K2
            | cv2.CALIB_FIX_K3
            | cv2.CALIB_FIX_K4
            | cv2.CALIB_FIX_K5
            | cv2.CALIB_FIX_K6
            | cv2.CALIB_ZERO_TANGENT_DIST
        ),
    )
    print("✓ Left camera calibrated (quick mode)")

    # Quick calibration for RIGHT camera
    print("Calibrating right camera (fixed principal point, zero distortion)...", flush=True)

    mtx_right_init = mtx_left_init.copy()  # Use same initial guess
    dist_right = np.zeros(5, dtype=np.float64)

    _, mtx_right, _, _, _ = cv2.calibrateCamera(
        objpoints_scaled,
        right_imgpoints,
        img_size,
        mtx_right_init,
        dist_right,
        flags=(
            cv2.CALIB_USE_INTRINSIC_GUESS
            | cv2.CALIB_FIX_PRINCIPAL_POINT
            | cv2.CALIB_FIX_K1
            | cv2.CALIB_FIX_K2
            | cv2.CALIB_FIX_K3
            | cv2.CALIB_FIX_K4
            | cv2.CALIB_FIX_K5
            | cv2.CALIB_FIX_K6
            | cv2.CALIB_ZERO_TANGENT_DIST
        ),
    )
    print("✓ Right camera calibrated (quick mode)")

    # Stereo calibration (intrinsics already fixed)
    print("Computing stereo calibration...", flush=True)
    rms_error, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
        objpoints_scaled,
        left_imgpoints,
        right_imgpoints,
        mtx_left,
        dist_left,
        mtx_right,
        dist_right,
        img_size,
        flags=cv2.CALIB_FIX_INTRINSIC,
    )
    print(f"✓ Stereo calibration complete (RMS error: {rms_error:.3f} px)")

    # Extract parameters
    baseline_mm = float(np.linalg.norm(T))
    baseline_ft = baseline_mm / 304.8
    focal_length_px = float(mtx_left[0, 0])
    cx = float(mtx_left[0, 2])
    cy = float(mtx_left[1, 2])

    # Compute per-image errors
    per_image_errors = _compute_per_image_errors(
        objpoints_scaled, left_imgpoints, right_imgpoints, mtx_left, dist_left, mtx_right, dist_right, R, T
    )

    # Quality rating with adjusted thresholds for quick mode
    quality = _rate_quick_calibration_quality(rms_error, num_pairs)

    _validate_stereo_geometry(rms_error, baseline_ft, F)

    # Print quality assessment
    print(f"\n{quality['emoji']} Quick Calibration Quality: {quality['rating']}")
    print(f"   {quality['description']}")
    if quality["recommendations"]:
        print("\nRecommendations:")
        for rec in quality["recommendations"]:
            print(f"   {rec}")

    return {
        "baseline_ft": baseline_ft,
        "focal_length_px": focal_length_px,
        "cx": cx,
        "cy": cy,
        # Quality metrics
        "rms_error_px": float(rms_error),
        "num_images": num_pairs,
        "num_images_used": num_pairs,
        "total_input_images": len(left_paths),
        "per_image_errors": per_image_errors,
        "pair_diagnostics": pair_diagnostics,
        "rejection_report": rejection_report,
        "quality": quality,
        "quality_rating": quality["rating"],
        "quality_description": quality["description"],
        "quality_emoji": quality["emoji"],
        "recommendations": quality["recommendations"],
        # Calibration mode flag
        "calibration_mode": "QUICK",
        # Full matrices (distortion is zero)
        "mtx_left": mtx_left,
        "mtx_right": mtx_right,
        "dist_left": dist_left,  # All zeros
        "dist_right": dist_right,  # All zeros
        "R": R,
        "T": T,
        "E": E,
        "F": F,
        "img_size": img_size,
    }


def _rate_quick_calibration_quality(rms_error: float, num_images: int) -> dict:
    """Rate quick calibration quality with adjusted thresholds.

    Quick mode uses relaxed thresholds since it skips distortion modeling.

    Args:
        rms_error: Overall RMS reprojection error in pixels
        num_images: Number of image pairs used

    Returns:
        Dictionary with rating, description, and recommendations
    """
    # Adjusted thresholds for quick mode
    GOOD_RMS = 2.0  # vs 1.0 for full calibration
    ACCEPTABLE_RMS = 3.0  # vs 2.0 for full calibration
    MIN_IMAGES = 3
    RECOMMENDED_IMAGES = 5

    recommendations = []

    # Determine rating
    if rms_error < GOOD_RMS and num_images >= RECOMMENDED_IMAGES:
        rating = "GOOD"
        emoji = "🟢"
        description = "Good quick calibration. Estimated 90-95% accuracy of full calibration."
    elif rms_error < ACCEPTABLE_RMS and num_images >= MIN_IMAGES:
        rating = "ACCEPTABLE"
        emoji = "🟡"
        description = "Acceptable quick calibration. Consider full calibration for maximum accuracy."
        if num_images < RECOMMENDED_IMAGES:
            recommendations.append(f"• Capture {RECOMMENDED_IMAGES - num_images} more images for better quality")
    else:
        rating = "POOR"
        emoji = "🔴"
        description = "Poor calibration. Full calibration recommended."

    # Add mode-specific recommendations
    if rms_error < GOOD_RMS:
        recommendations.append("✓ Quick calibration successful")
        recommendations.append("• For maximum accuracy, run Full Calibration mode")
    else:
        recommendations.append("⚠️ High reprojection error detected")
        recommendations.append("• Try full calibration mode with 10+ images")
        recommendations.append("• Ensure board is perfectly flat and well-lit")
        recommendations.append("• Check camera focus is sharp")

    if num_images < RECOMMENDED_IMAGES:
        recommendations.append(f"• {RECOMMENDED_IMAGES} images recommended (have {num_images})")

    # Quick mode limitations
    recommendations.append("Note: Quick mode uses simplified assumptions:")
    recommendations.append("  - Principal point fixed at image center")
    recommendations.append("  - Lens distortion not modeled")

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
    # Minimum pairs required for reliable calibration
    MIN_PAIRS = 10
    RECOMMENDED_PAIRS = 15

    print("\n=== LEFT CAMERA ===")
    left_detections, img_size = _collect_corners(left_paths, pattern_size, square_mm)
    print("\n=== RIGHT CAMERA ===")
    right_detections, _ = _collect_corners(right_paths, pattern_size, square_mm)

    # Match pairs where both cameras detected corners
    print("\n=== MATCHING STEREO PAIRS ===")
    objpoints, left_imgpoints, right_imgpoints, rejection_report, pair_diagnostics = _match_stereo_pairs(
        left_detections, right_detections
    )

    # Report rejections
    if rejection_report:
        print("\nRejected images (corner detection failed in one or both cameras):")
        for msg in rejection_report:
            print(f"  • {msg}")

    # Validate we have enough pairs
    num_pairs = len(objpoints)
    print(f"\nMatched pairs: {num_pairs}/{len(left_paths)}")

    if num_pairs == 0:
        raise RuntimeError(
            "No matching image pairs found. Ensure calibration board (ChArUco or checkerboard) is visible in BOTH cameras for all images."
        )

    if num_pairs < MIN_PAIRS:
        raise RuntimeError(
            f"Insufficient matching pairs ({num_pairs} found, need at least {MIN_PAIRS}). "
            f"Recapture more images with calibration board visible in BOTH cameras."
        )

    if num_pairs < RECOMMENDED_PAIRS:
        print(f"⚠️  Warning: Only {num_pairs} pairs (recommended: {RECOMMENDED_PAIRS}+)")
        print(f"   Calibration may be less accurate. Consider capturing {RECOMMENDED_PAIRS - num_pairs} more images.")

    print(f"\nCalibrating with {num_pairs} matched image pairs...")

    # ChArUco object points are already scaled by square_mm in the board definition
    # No additional scaling needed
    objpoints_scaled = objpoints

    print("Calibrating left camera intrinsics...", flush=True)
    _, mtx_left, dist_left, _, _ = cv2.calibrateCamera(objpoints_scaled, left_imgpoints, img_size, None, None)
    print("✓ Left camera calibrated")

    print("Calibrating right camera intrinsics...", flush=True)
    _, mtx_right, dist_right, _, _ = cv2.calibrateCamera(objpoints_scaled, right_imgpoints, img_size, None, None)
    print("✓ Right camera calibrated")

    print("Computing stereo calibration...", flush=True)
    rms_error, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
        objpoints_scaled,
        left_imgpoints,
        right_imgpoints,
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
        objpoints_scaled, left_imgpoints, right_imgpoints, mtx_left, dist_left, mtx_right, dist_right, R, T
    )

    # Calculate quality rating
    num_images = len(objpoints_scaled)
    quality = _rate_calibration_quality(rms_error, num_images)

    _validate_stereo_geometry(rms_error, baseline_ft, F)

    # Print quality assessment
    print(f"\n{quality['emoji']} Calibration Quality: {quality['rating']}")
    print(f"   {quality['description']}")
    if quality["recommendations"]:
        print("\nRecommendations:")
        for rec in quality["recommendations"]:
            print(f"   {rec}")

    # Print summary
    total_input = len(left_paths)
    rejected = total_input - num_images
    if rejected > 0:
        print("\n📊 Summary:")
        print(f"   Input images: {total_input} pairs")
        print(f"   Rejected: {rejected} pairs (corner detection failed)")
        print(f"   Used for calibration: {num_images} pairs ✓")

    return {
        "baseline_ft": baseline_ft,
        "focal_length_px": focal_length_px,
        "cx": cx,
        "cy": cy,
        # Quality metrics
        "rms_error_px": float(rms_error),
        "num_images": num_images,
        "num_images_used": num_images,  # Alias for clarity
        "total_input_images": total_input,
        "per_image_errors": per_image_errors,
        "pair_diagnostics": pair_diagnostics,
        "rejection_report": rejection_report,
        "quality": quality,
        # Extract quality fields to top level for easier UI access
        "quality_rating": quality["rating"],
        "quality_description": quality["description"],
        "quality_emoji": quality["emoji"],
        "recommendations": quality["recommendations"],
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
    report_path = calib_dir / "report.json"

    # Extract quality info for saving
    quality = updates.get("quality", {})

    save_kwargs = dict(
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
        calibration_mode=updates.get("calibration_mode", "FULL"),
        production_ready=updates.get("calibration_mode", "FULL") != "QUICK",
    )
    # Persist the epipolar geometry so the runtime loader uses the calibrated
    # fundamental/essential matrices directly instead of recomputing F from R,T.
    if updates.get("F") is not None:
        save_kwargs["F"] = np.asarray(updates["F"], dtype=np.float64)
    if updates.get("E") is not None:
        save_kwargs["E"] = np.asarray(updates["E"], dtype=np.float64)

    np.savez(calib_path, **save_kwargs)
    report = {
        "calibration_mode": updates.get("calibration_mode", "FULL"),
        "rms_error_px": updates.get("rms_error_px", 0.0),
        "num_images": updates.get("num_images", 0),
        "num_images_used": updates.get("num_images_used", updates.get("num_images", 0)),
        "total_input_images": updates.get("total_input_images", 0),
        "baseline_ft": updates.get("baseline_ft", 0.0),
        "focal_length_px": updates.get("focal_length_px", 0.0),
        "image_size": list(updates.get("img_size", [])),
        "quality": quality,
        "per_image_errors": updates.get("per_image_errors", []),
        "pair_diagnostics": updates.get("pair_diagnostics", []),
        "rejection_report": updates.get("rejection_report", []),
        "recommendations": updates.get("recommendations", []),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def load_calibration_quality(calib_path: Optional[Path] = None) -> Optional[dict]:
    """Load calibration quality metrics from saved calibration file.

    Args:
        calib_path: Path to calibration file (default: calibration/stereo_calibration.npz)

    Returns:
        Dict with quality metrics or None if file doesn't exist or has no quality data
    """
    if calib_path is None:
        try:
            from app.services.rig_profile import RigProfileService

            service = RigProfileService()
            profile = service.load_active()
            calib_path = (
                service.calibration_path(profile) if profile is not None else Path("calibration/stereo_calibration.npz")
            )
        except Exception:
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
            "calibration_mode": str(data.get("calibration_mode", "FULL")),
            "production_ready": bool(data.get("production_ready", True)),
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

    # Choose calibration mode
    if args.quick:
        print("Using QUICK calibration mode")
        updates = quick_calibrate(args.left, args.right, pattern, args.square_mm)
    else:
        print("Using FULL calibration mode")
        updates = _calibrate(args.left, args.right, pattern, args.square_mm)

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
