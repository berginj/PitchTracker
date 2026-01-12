"""Pipeline runner wiring capture, detection, lane gating, and stereo matching."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, List

from capture import CameraDevice, SimulatedCamera, UvcCamera
from capture.opencv_backend import OpenCVCamera
from configs.lane_io import load_lane_rois
from configs.roi_io import load_rois
from configs.settings import load_config
from contracts import Detection
from detect import LaneGate, LaneRoi
from detect.classical_detector import ClassicalDetector
from detect.ml_detector import MlDetector
from detect.config import DetectorConfig, FilterConfig, Mode
from stereo import StereoLaneGate
from stereo.association import StereoMatch
from metrics.simple_metrics import compute_plate_stub

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pitch pipeline with lane gating.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--roi", type=Path, default=Path("configs/roi.json"))
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--stereo", action="store_true", help="Enable stereo matching")
    parser.add_argument(
        "--backend",
        choices=("uvc", "opencv", "sim"),
        default="uvc",
        help="Capture backend to use (opencv or sim).",
    )
    parser.add_argument("--left", default="left", help="Left camera ID or index.")
    parser.add_argument("--right", default="right", help="Right camera ID or index.")
    return parser.parse_args()


def build_lane_gate(
    width: int,
    height: int,
    left_id: str,
    right_id: str,
    lane_polygon: list[tuple[float, float]] | None,
) -> LaneGate:
    if lane_polygon:
        roi = LaneRoi(polygon=lane_polygon)
    else:
        roi = LaneRoi(
            polygon=[
                (width * 0.25, height * 0.25),
                (width * 0.75, height * 0.25),
                (width * 0.75, height * 0.75),
                (width * 0.25, height * 0.75),
            ]
        )
    return LaneGate(roi_by_camera={left_id: roi, right_id: roi})


def load_lane_polygon(
    roi_path: Path, left_id: str, right_id: str
) -> list[tuple[float, float]] | None:
    rois = load_rois(roi_path)
    lane = rois.get("lane")
    if lane:
        return [(float(x), float(y)) for x, y in lane]
    legacy = load_lane_rois(Path("configs/lane_roi.json"))
    if left_id in legacy:
        return [(float(x), float(y)) for x, y in legacy[left_id].polygon]
    if right_id in legacy:
        return [(float(x), float(y)) for x, y in legacy[right_id].polygon]
    return None


def load_plate_polygon(roi_path: Path) -> list[tuple[float, float]] | None:
    rois = load_rois(roi_path)
    plate = rois.get("plate")
    if plate:
        return [(float(x), float(y)) for x, y in plate]
    return None


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


def configure_camera(camera: CameraDevice, config: object) -> None:
    camera.set_mode(
        config.camera.width,
        config.camera.height,
        config.camera.fps,
        config.camera.pixfmt,
    )
    camera.set_controls(
        config.camera.exposure_us,
        config.camera.gain,
        config.camera.wb_mode,
        config.camera.wb,
    )


def run_pipeline(
    frames: int,
    enable_stereo: bool,
    config_path: Path,
    roi_path: Path,
    backend: str,
    left_id: str,
    right_id: str,
) -> None:
    config = load_config(config_path)
    if backend == "opencv":
        left = OpenCVCamera()
        right = OpenCVCamera()
    else:
        if backend == "uvc":
            left = UvcCamera()
            right = UvcCamera()
        else:
            left = SimulatedCamera()
            right = SimulatedCamera()
    left.open(left_id)
    right.open(right_id)
    configure_camera(left, config)
    configure_camera(right, config)

    filter_cfg = FilterConfig(
        min_area=config.detector.filters.min_area,
        max_area=config.detector.filters.max_area,
        min_circularity=config.detector.filters.min_circularity,
        max_circularity=config.detector.filters.max_circularity,
        min_velocity=config.detector.filters.min_velocity,
        max_velocity=config.detector.filters.max_velocity,
    )
    if config.detector.type == "ml":
        detector = MlDetector(
            model_path=config.detector.model_path,
            input_size=config.detector.model_input_size,
            conf_threshold=config.detector.model_conf_threshold,
            class_id=config.detector.model_class_id,
            output_format=config.detector.model_format,
        )
    else:
        detector_cfg = DetectorConfig(
            frame_diff_threshold=config.detector.frame_diff_threshold,
            bg_diff_threshold=config.detector.bg_diff_threshold,
            bg_alpha=config.detector.bg_alpha,
            edge_threshold=config.detector.edge_threshold,
            blob_threshold=config.detector.blob_threshold,
            runtime_budget_ms=config.detector.runtime_budget_ms,
            crop_padding_px=config.detector.crop_padding_px,
            min_consecutive=config.detector.min_consecutive,
            filters=filter_cfg,
        )
        detector = ClassicalDetector(
            config=detector_cfg,
            mode=Mode(config.detector.mode),
            roi_by_camera=(
                {left_id: lane_polygon, right_id: lane_polygon}
                if lane_polygon
                else None
            ),
        )
    lane_polygon = load_lane_polygon(roi_path, left_id, right_id)
    lane_gate = build_lane_gate(
        config.camera.width,
        config.camera.height,
        left_id,
        right_id,
        lane_polygon,
    )
    plate_polygon = load_plate_polygon(roi_path)
    plate_gate = None
    if plate_polygon:
        plate_roi = LaneRoi(polygon=plate_polygon)
        plate_gate = LaneGate(roi_by_camera={left_id: plate_roi, right_id: plate_roi})
        plate_stereo_gate = StereoLaneGate(lane_gate=plate_gate)
    else:
        plate_stereo_gate = None
    stereo_gate = StereoLaneGate(lane_gate=lane_gate)

    try:
        for _ in range(frames):
            left_frame = left.read_frame(timeout_ms=50)
            right_frame = right.read_frame(timeout_ms=50)
            detections = detector.detect(left_frame) + detector.detect(right_frame)
            gated = gate_detections(lane_gate, detections, left_frame.frame_index)
            if plate_gate:
                plate_gated = gate_detections(plate_gate, gated, left_frame.frame_index)
            else:
                plate_gated = []
            LOGGER.info(
                "frame=%s detections=%s gated=%s plate_gated=%s",
                left_frame.frame_index,
                len(detections),
                len(gated),
                len(plate_gated),
            )
            if enable_stereo:
                left_gated = [d for d in gated if d.camera_id == left_id]
                right_gated = [d for d in gated if d.camera_id == right_id]
                matches = build_stereo_matches(left_gated, right_gated)
                gated_matches = stereo_gate.filter_matches(matches)
                if plate_stereo_gate:
                    plate_matches = plate_stereo_gate.filter_matches(gated_matches)
                else:
                    plate_matches = []
                plate_metrics = compute_plate_stub(plate_matches)
                LOGGER.info(
                    "frame=%s stereo_matches=%s stereo_gated=%s plate_matches=%s run_in=%.2f rise_in=%.2f",
                    left_frame.frame_index,
                    len(matches),
                    len(gated_matches),
                    len(plate_matches),
                    plate_metrics.run_in,
                    plate_metrics.rise_in,
                )
    finally:
        left.close()
        right.close()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_pipeline(
        args.frames,
        args.stereo,
        args.config,
        args.roi,
        args.backend,
        args.left,
        args.right,
    )


if __name__ == "__main__":
    main()
