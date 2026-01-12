"""Analyze recorded video for ball size and lighting metrics."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from configs.roi_io import load_rois
from configs.settings import load_config
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
from contracts import Frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a recorded video for ball metrics.")
    parser.add_argument("--video", type=Path, required=True, help="Video path.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--roi", type=Path, default=Path("configs/roi.json"))
    parser.add_argument("--out", type=Path, default=Path("analysis.csv"))
    parser.add_argument("--camera-id", default="left", help="Camera id label.")
    return parser.parse_args()


def build_detector(config_path: Path, roi_path: Path, camera_id: str) -> ClassicalDetector:
    config = load_config(config_path)
    cfg = config.detector
    filter_cfg = FilterConfig(
        min_area=cfg.filters.min_area,
        max_area=cfg.filters.max_area,
        min_circularity=cfg.filters.min_circularity,
        max_circularity=cfg.filters.max_circularity,
        min_velocity=cfg.filters.min_velocity,
        max_velocity=cfg.filters.max_velocity,
    )
    detector_cfg = CvDetectorConfig(
        frame_diff_threshold=cfg.frame_diff_threshold,
        bg_diff_threshold=cfg.bg_diff_threshold,
        bg_alpha=cfg.bg_alpha,
        edge_threshold=cfg.edge_threshold,
        blob_threshold=cfg.blob_threshold,
        runtime_budget_ms=cfg.runtime_budget_ms,
        crop_padding_px=cfg.crop_padding_px,
        filters=filter_cfg,
    )
    rois = load_rois(roi_path)
    lane = rois.get("lane")
    roi_by_camera = None
    if lane:
        roi_by_camera = {camera_id: [(float(x), float(y)) for x, y in lane]}
    return ClassicalDetector(config=detector_cfg, mode=Mode(cfg.mode), roi_by_camera=roi_by_camera)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    detector = build_detector(args.config, args.roi, args.camera_id)
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"Failed to open {args.video}")

    with args.out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "frame_index",
                "mean_gray",
                "std_gray",
                "detection_count",
                "best_radius_px",
                "best_confidence",
                "best_u",
                "best_v",
                "exposure_us",
                "gain",
            ]
        )
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            if frame.ndim == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            mean_gray = float(np.mean(gray))
            std_gray = float(np.std(gray))
            frame_obj = Frame(
                camera_id=args.camera_id,
                frame_index=frame_index,
                t_capture_monotonic_ns=0,
                image=gray,
                width=gray.shape[1],
                height=gray.shape[0],
                pixfmt=config.camera.pixfmt,
            )
            detections = detector.detect(frame_obj)
            best = max(detections, key=lambda det: det.confidence, default=None)
            writer.writerow(
                [
                    frame_index,
                    f"{mean_gray:.3f}",
                    f"{std_gray:.3f}",
                    len(detections),
                    f"{best.radius_px:.2f}" if best else "",
                    f"{best.confidence:.3f}" if best else "",
                    f"{best.u:.2f}" if best else "",
                    f"{best.v:.2f}" if best else "",
                    config.camera.exposure_us,
                    config.camera.gain,
                ]
            )

    capture.release()
    print(f"Wrote analysis to {args.out}")


if __name__ == "__main__":
    main()
