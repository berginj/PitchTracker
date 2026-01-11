"""Minimal dual-camera preview with lane ROI drawing."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from capture.opencv_backend import OpenCVCamera
from configs.settings import load_config
from ui.preview import PreviewState, run_preview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview two cameras and draw lane ROI.")
    parser.add_argument("--left", type=str, default="0")
    parser.add_argument("--right", type=str, default="1")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--lane", type=Path, default=Path("configs/lane_roi.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    left = OpenCVCamera()
    right = OpenCVCamera()
    left.open(args.left)
    right.open(args.right)
    left.set_mode(config.camera.width, config.camera.height, config.camera.fps, config.camera.pixfmt)
    right.set_mode(config.camera.width, config.camera.height, config.camera.fps, config.camera.pixfmt)

    left_frame = left.read_frame(timeout_ms=100).image
    right_frame = right.read_frame(timeout_ms=100).image
    if config.camera.pixfmt == "GRAY8":
        left_frame = cv2.cvtColor(left_frame, cv2.COLOR_GRAY2BGR)
        right_frame = cv2.cvtColor(right_frame, cv2.COLOR_GRAY2BGR)

    run_preview(
        window_name="Pitch Tracker Preview",
        left_frame=left_frame,
        right_frame=right_frame,
        lane_path=args.lane,
        left_id=args.left,
        right_id=args.right,
        state=PreviewState(points=[]),
    )

    left.close()
    right.close()


if __name__ == "__main__":
    main()
