"""Image loading and calibration artifact persistence for stereo calibration."""

from __future__ import annotations

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


def _collect_corners(
    paths: List[Path],
    pattern_size: Tuple[int, int],
    square_mm: float,
) -> Tuple[List[CornerDetection], Tuple[int, int]]:
    """Detect calibration board corners in images.

    Tries ChArUco board detection first, falls back to plain checkerboard
    if no markers found.

    Returns:
        detections: CornerDetection records for successful detections
        img_size: Image dimensions (width, height)
    """
    detections: List[CornerDetection] = []
    img_size: Tuple[int, int] | None = None

    from calib.charuco import get_dictionary, make_charuco_board

    aruco_dict = get_dictionary()
    board = make_charuco_board(pattern_size[0], pattern_size[1], square_mm, aruco_dict)

    try:
        detector_params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
    except AttributeError:
        detector_params = cv2.aruco.DetectorParameters_create()
        detector = None

    print(f"Processing {len(paths)} images for calibration board detection "
          "(ChArUco with checkerboard fallback)...")
    for i, path in enumerate(paths):
        print(f"  [{i+1}/{len(paths)}] {path.name}...", end=" ", flush=True)
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            print("❌ Failed to load")
            continue
        img_size = (image.shape[1], image.shape[0])

        charuco_det = _try_charuco_detection(
            image, board, aruco_dict, detector_params, detector, i, path, square_mm
        )
        if charuco_det is not None:
            detections.append(charuco_det)
            continue

        checker_det = _try_checkerboard_fallback(
            image, pattern_size, square_mm, i, path
        )
        if checker_det is not None:
            detections.append(checker_det)
        else:
            print("❌ No ChArUco markers and no checkerboard pattern")

    print(f"Found calibration corners in {len(detections)} images "
          "(ChArUco or checkerboard)")
    if img_size is None:
        raise RuntimeError("No valid images found for calibration.")
    return detections, img_size


def _try_charuco_detection(
    image: np.ndarray,
    board: object,
    aruco_dict: object,
    detector_params: object,
    detector: object | None,
    index: int,
    path: Path,
    square_mm: float,
) -> Optional[CornerDetection]:
    """Attempt ChArUco corner detection on a single image."""
    if detector is not None:
        marker_corners, marker_ids, _ = detector.detectMarkers(image)
    else:
        marker_corners, marker_ids, _ = cv2.aruco.detectMarkers(
            image, aruco_dict, parameters=detector_params
        )

    if marker_ids is None or len(marker_ids) == 0:
        return None

    try:
        num_corners, charuco_corners, charuco_ids = \
            cv2.aruco.interpolateCornersCharuco(
                marker_corners, marker_ids, image, board
            )
    except TypeError:
        num_corners, charuco_corners, charuco_ids = \
            cv2.aruco.interpolateCornersCharuco(
                marker_corners, marker_ids, image, board
            )

    MIN_CORNERS = 4
    if num_corners is None or num_corners < MIN_CORNERS:
        return None

    try:
        obj_pts = board.getChessboardCorners()[charuco_ids.flatten()]
    except AttributeError:
        obj_pts = board.chessboardCorners[charuco_ids.flatten()]

    print(f"✓ ({num_corners} ChArUco corners)")
    return CornerDetection(
        index=index,
        path=path,
        objpoints=np.asarray(obj_pts, dtype=np.float32),
        imgpoints=np.asarray(charuco_corners, dtype=np.float32),
        kind="charuco",
        corner_ids=np.asarray(charuco_ids, dtype=np.int32).reshape(-1),
    )


def _try_checkerboard_fallback(
    image: np.ndarray,
    pattern_size: Tuple[int, int],
    square_mm: float,
    index: int,
    path: Path,
) -> Optional[CornerDetection]:
    """Attempt plain checkerboard detection as fallback."""
    board_size = (pattern_size[0] - 1, pattern_size[1] - 1)

    flag_combinations = [
        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE,
        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        + cv2.CALIB_CB_FAST_CHECK,
        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        + cv2.CALIB_CB_FILTER_QUADS,
        cv2.CALIB_CB_ADAPTIVE_THRESH,
        cv2.CALIB_CB_NORMALIZE_IMAGE,
    ]

    ret = False
    corners = None
    for flags in flag_combinations:
        ret, corners = cv2.findChessboardCorners(image, board_size, flags)
        if ret and corners is not None:
            break

    if not ret or corners is None:
        return None

    criteria = (
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001
    )
    corners_refined = cv2.cornerSubPix(
        image, corners, (11, 11), (-1, -1), criteria
    )

    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[
        0: board_size[0], 0: board_size[1]
    ].T.reshape(-1, 2)
    objp *= square_mm

    print(f"✓ ({len(corners_refined)} checkerboard corners)")
    return CornerDetection(
        index=index,
        path=path,
        objpoints=objp,
        imgpoints=np.asarray(corners_refined, dtype=np.float32),
        kind="checkerboard",
    )


def _write_config(config_path: Path, updates: dict) -> None:
    """Write scalar calibration values to YAML config."""
    data = yaml.safe_load(config_path.read_text())
    data.setdefault("stereo", {})

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

    quality = updates.get("quality", {})

    save_kwargs = dict(
        mtx_left=updates["mtx_left"],
        mtx_right=updates["mtx_right"],
        dist_left=updates["dist_left"],
        dist_right=updates["dist_right"],
        R=updates["R"],
        T=updates["T"],
        img_size=updates["img_size"],
        baseline_ft=updates["baseline_ft"],
        focal_length_px=updates["focal_length_px"],
        cx=updates["cx"],
        cy=updates["cy"],
        rms_error_px=updates.get("rms_error_px", 0.0),
        num_images=updates.get("num_images", 0),
        per_image_errors=updates.get("per_image_errors", []),
        quality_rating=quality.get("rating", "UNKNOWN"),
        quality_description=quality.get("description", ""),
        calibration_mode=updates.get("calibration_mode", "FULL"),
        production_ready=updates.get("calibration_mode", "FULL") != "QUICK",
    )
    if updates.get("F") is not None:
        save_kwargs["F"] = np.asarray(updates["F"], dtype=np.float64)
    if updates.get("E") is not None:
        save_kwargs["E"] = np.asarray(updates["E"], dtype=np.float64)

    np.savez(calib_path, **save_kwargs)

    report = {
        "calibration_mode": updates.get("calibration_mode", "FULL"),
        "rms_error_px": updates.get("rms_error_px", 0.0),
        "num_images": updates.get("num_images", 0),
        "num_images_used": updates.get(
            "num_images_used", updates.get("num_images", 0)
        ),
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


def load_calibration_quality(
    calib_path: Optional[Path] = None,
) -> Optional[dict]:
    """Load calibration quality metrics from saved calibration file.

    Args:
        calib_path: Path to calibration file
            (default: calibration/stereo_calibration.npz)

    Returns:
        Dict with quality metrics or None if file doesn't exist
    """
    if calib_path is None:
        try:
            from app.services.rig_profile import RigProfileService

            service = RigProfileService()
            profile = service.load_active()
            calib_path = (
                service.calibration_path(profile)
                if profile is not None
                else Path("calibration/stereo_calibration.npz")
            )
        except Exception:
            calib_path = Path("calibration/stereo_calibration.npz")

    if not calib_path.exists():
        return None

    try:
        data = np.load(calib_path, allow_pickle=True)

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
