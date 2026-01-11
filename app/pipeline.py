"""Pipeline runner wiring capture, detection, lane gating, and stereo matching."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, List

from capture import CameraDevice, SimulatedCamera
from configs.settings import load_config
from contracts import Detection
from detect import LaneGate, LaneRoi
from detect.simple_detector import CenterDetector
from stereo import StereoLaneGate
from stereo.association import StereoMatch

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pitch pipeline with lane gating.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--stereo", action="store_true", help="Enable stereo matching")
    return parser.parse_args()


def build_lane_gate(width: int, height: int) -> LaneGate:
    roi = LaneRoi(
        polygon=[
            (width * 0.25, height * 0.25),
            (width * 0.75, height * 0.25),
            (width * 0.75, height * 0.75),
            (width * 0.25, height * 0.75),
        ]
    )
    return LaneGate(roi_by_camera={"left": roi, "right": roi})


def gate_detections(
    lane_gate: LaneGate, detections: Iterable[Detection], frame_index: int
) -> List[Detection]:
    allowed = lane_gate.filter_detections(detections)
    allowed_set = set(allowed)
    dropped = [detection for detection in detections if detection not in allowed_set]
    if dropped:
        LOGGER.info(
            "frame=%s dropped_out_of_lane=%s detections=%s",
            frame_index,
            len(dropped),
            dropped,
        )
    return allowed


def build_stereo_matches(
    left_detections: Iterable[Detection],
    right_detections: Iterable[Detection],
) -> List[StereoMatch]:
    matches: List[StereoMatch] = []
    for left in left_detections:
        for right in right_detections:
            matches.append(
                StereoMatch(
                    left=left,
                    right=right,
                    epipolar_error_px=abs(left.v - right.v),
                    score=min(left.confidence, right.confidence),
                )
            )
    return matches


def run_pipeline(frames: int, enable_stereo: bool, config_path: Path) -> None:
    config = load_config(config_path)
    left: CameraDevice = SimulatedCamera()
    right: CameraDevice = SimulatedCamera()
    left.open("left")
    right.open("right")
    left.set_mode(config.camera.width, config.camera.height, config.camera.fps, config.camera.pixfmt)
    right.set_mode(config.camera.width, config.camera.height, config.camera.fps, config.camera.pixfmt)
    left.set_controls(config.camera.exposure_us, config.camera.gain, config.camera.wb_mode, config.camera.wb)
    right.set_controls(config.camera.exposure_us, config.camera.gain, config.camera.wb_mode, config.camera.wb)

    detector = CenterDetector()
    lane_gate = build_lane_gate(config.camera.width, config.camera.height)
    stereo_gate = StereoLaneGate(lane_gate=lane_gate)

    try:
        for _ in range(frames):
            left_frame = left.read_frame(timeout_ms=50)
            right_frame = right.read_frame(timeout_ms=50)
            detections = detector.detect(left_frame) + detector.detect(right_frame)
            gated = gate_detections(lane_gate, detections, left_frame.frame_index)
            LOGGER.info(
                "frame=%s detections=%s gated=%s",
                left_frame.frame_index,
                len(detections),
                len(gated),
            )
            if enable_stereo:
                left_gated = [d for d in gated if d.camera_id == "left"]
                right_gated = [d for d in gated if d.camera_id == "right"]
                matches = build_stereo_matches(left_gated, right_gated)
                gated_matches = stereo_gate.filter_matches(matches)
                LOGGER.info(
                    "frame=%s stereo_matches=%s stereo_gated=%s",
                    left_frame.frame_index,
                    len(matches),
                    len(gated_matches),
                )
    finally:
        left.close()
        right.close()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_pipeline(args.frames, args.stereo, args.config)


if __name__ == "__main__":
    main()
