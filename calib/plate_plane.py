"""Estimate plate plane Z using stereo images and update config."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml

from configs.settings import load_config
from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate plate Z from stereo images.")
    parser.add_argument("--left", type=Path, required=True, help="Left image path.")
    parser.add_argument("--right", type=Path, required=True, help="Right image path.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--write", action="store_true", help="Write plate Z to config.")
    return parser.parse_args()


def _detect_plate_center(image: np.ndarray) -> Optional[tuple[float, float]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0.0
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
        if len(approx) == 5:
            area = cv2.contourArea(approx)
            if area > best_area:
                best_area = area
                best = approx
    if best is None:
        return None
    moments = cv2.moments(best)
    if moments["m00"] == 0:
        return None
    cx = moments["m10"] / moments["m00"]
    cy = moments["m01"] / moments["m00"]
    return (cx, cy)


def _estimate_plate_z(config_path: Path, left: Path, right: Path) -> Optional[float]:
    config = load_config(config_path)
    left_img = cv2.imread(str(left))
    right_img = cv2.imread(str(right))
    if left_img is None or right_img is None:
        return None
    left_center = _detect_plate_center(left_img)
    right_center = _detect_plate_center(right_img)
    if left_center is None or right_center is None:
        return None
    cx = config.stereo.cx or (config.camera.width / 2.0)
    cy = config.stereo.cy or (config.camera.height / 2.0)
    matcher = SimpleStereoMatcher(
        StereoGeometry(
            baseline_ft=config.stereo.baseline_ft,
            focal_length_px=config.stereo.focal_length_px,
            cx=float(cx),
            cy=float(cy),
            epipolar_epsilon_px=float(config.stereo.epipolar_epsilon_px),
            z_min_ft=float(config.stereo.z_min_ft),
            z_max_ft=float(config.stereo.z_max_ft),
        )
    )
    disparity = left_center[0] - right_center[0]
    if abs(disparity) < 0.5:
        return None
    z_ft = (config.stereo.focal_length_px * config.stereo.baseline_ft) / disparity
    return float(z_ft)


def _write_plate_z(config_path: Path, plate_z_ft: float) -> None:
    data = yaml.safe_load(config_path.read_text())
    data.setdefault("metrics", {})
    data["metrics"]["plate_plane_z_ft"] = plate_z_ft
    config_path.write_text(yaml.safe_dump(data, sort_keys=False))


def log_plate_plane_result(config_path: Path, success: bool, plate_z_ft: Optional[float]) -> None:
    log_path = config_path.parent / "plate_plane_log.csv"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    header = "timestamp_utc,success,plate_z_ft\n"
    if not log_path.exists():
        log_path.write_text(header)
    with log_path.open("a", newline="") as handle:
        handle.write(f"{timestamp},{int(success)},{plate_z_ft if plate_z_ft is not None else ''}\n")


def estimate_and_write(left: Path, right: Path, config_path: Path) -> float:
    plate_z_ft = _estimate_plate_z(config_path, left, right)
    if plate_z_ft is None:
        log_plate_plane_result(config_path, False, None)
        raise RuntimeError("Failed to estimate plate Z from images.")
    _write_plate_z(config_path, plate_z_ft)
    log_plate_plane_result(config_path, True, plate_z_ft)
    return plate_z_ft


def main() -> None:
    args = parse_args()
    plate_z_ft = _estimate_plate_z(args.config, args.left, args.right)
    if plate_z_ft is None:
        log_plate_plane_result(args.config, False, None)
        raise RuntimeError("Failed to estimate plate Z from images.")
    print(f"Estimated plate_plane_z_ft: {plate_z_ft:.3f}")
    if args.write:
        _write_plate_z(args.config, plate_z_ft)
        log_plate_plane_result(args.config, True, plate_z_ft)
        print(f"Updated config: {args.config}")


if __name__ == "__main__":
    main()
