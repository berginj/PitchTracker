"""Minimal simulated pipeline demo."""

from __future__ import annotations

import argparse
from pathlib import Path

from capture import SimulatedCamera
from configs.settings import load_config
from detect import LaneGate, LaneRoi
from detect.simple_detector import CenterDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simulated pitch pipeline demo.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--frames", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    left = SimulatedCamera()
    right = SimulatedCamera()
    left.open("left")
    right.open("right")
    left.set_mode(config.camera.width, config.camera.height, config.camera.fps, config.camera.pixfmt)
    right.set_mode(config.camera.width, config.camera.height, config.camera.fps, config.camera.pixfmt)
    left.set_controls(config.camera.exposure_us, config.camera.gain, config.camera.wb_mode, config.camera.wb)
    right.set_controls(config.camera.exposure_us, config.camera.gain, config.camera.wb_mode, config.camera.wb)

    roi = LaneRoi(
        polygon=[
            (config.camera.width * 0.25, config.camera.height * 0.25),
            (config.camera.width * 0.75, config.camera.height * 0.25),
            (config.camera.width * 0.75, config.camera.height * 0.75),
            (config.camera.width * 0.25, config.camera.height * 0.75),
        ]
    )
    lane_gate = LaneGate(roi_by_camera={"left": roi, "right": roi})
    detector = CenterDetector()

    for _ in range(args.frames):
        left_frame = left.read_frame(timeout_ms=50)
        right_frame = right.read_frame(timeout_ms=50)
        detections = detector.detect(left_frame) + detector.detect(right_frame)
        gated = lane_gate.filter_detections(detections)
        print(
            f"frame={left_frame.frame_index} detections={len(detections)} gated={len(gated)}"
        )

    left.close()
    right.close()


if __name__ == "__main__":
    main()
