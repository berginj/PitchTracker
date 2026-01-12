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

    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            continue
        img_size = (image.shape[1], image.shape[0])
        found, corners = cv2.findChessboardCorners(image, pattern_size)
        if not found:
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

    if img_size is None:
        raise RuntimeError("No valid images found for calibration.")
    return objpoints, imgpoints, img_size


def _calibrate(
    left_paths: List[Path],
    right_paths: List[Path],
    pattern_size: Tuple[int, int],
    square_mm: float,
) -> dict:
    left_obj, left_img, img_size = _collect_corners(left_paths, pattern_size)
    right_obj, right_img, _ = _collect_corners(right_paths, pattern_size)
    if len(left_obj) != len(right_obj):
        raise RuntimeError("Left/right image counts do not match after corner detection.")
    if not left_obj:
        raise RuntimeError("No chessboard corners detected.")

    objp = left_obj[0].copy()
    objp[:, :2] *= float(square_mm)
    objpoints = [objp for _ in left_obj]

    _, mtx_left, dist_left, _, _ = cv2.calibrateCamera(
        objpoints, left_img, img_size, None, None
    )
    _, mtx_right, dist_right, _, _ = cv2.calibrateCamera(
        objpoints, right_img, img_size, None, None
    )

    _, _, _, _, _, R, T, _, _ = cv2.stereoCalibrate(
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

    baseline_mm = float(np.linalg.norm(T))
    baseline_ft = baseline_mm / 304.8
    focal_length_px = float(mtx_left[0, 0])
    cx = float(mtx_left[0, 2])
    cy = float(mtx_left[1, 2])

    return {
        "baseline_ft": baseline_ft,
        "focal_length_px": focal_length_px,
        "cx": cx,
        "cy": cy,
    }


def _write_config(config_path: Path, updates: dict) -> None:
    data = yaml.safe_load(config_path.read_text())
    data.setdefault("stereo", {})
    for key, value in updates.items():
        data["stereo"][key] = value
    config_path.write_text(yaml.safe_dump(data, sort_keys=False))


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
