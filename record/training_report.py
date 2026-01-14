"""Generate a training report from a recorded session (no video payloads)."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np

from configs.roi_io import load_rois
from configs.settings import load_config
from contracts import Frame
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
from detect.ml_detector import MlDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a training report from a session folder.")
    parser.add_argument("--session-dir", type=Path, required=True, help="Session directory path.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--roi", type=Path, default=Path("configs/roi.json"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--stride", type=int, default=1, help="Process every Nth frame.")
    parser.add_argument("--skip-detection", action="store_true", help="Skip detector stats.")
    parser.add_argument("--skip-brightness", action="store_true", help="Skip brightness stats.")
    parser.add_argument("--pitcher", default=None)
    parser.add_argument("--location-profile", default=None)
    parser.add_argument("--rig-id", default=None)
    parser.add_argument("--operator", default=None)
    parser.add_argument("--host", default=None)
    return parser.parse_args()


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = int(round((pct / 100.0) * (len(values) - 1)))
    return float(values[max(min(idx, len(values) - 1), 0)])


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _collect_pitch_dirs(session_dir: Path) -> List[Path]:
    pitch_dirs = []
    for child in session_dir.iterdir():
        if not child.is_dir():
            continue
        manifest = child / "manifest.json"
        if manifest.exists():
            pitch_dirs.append(child)
    return sorted(pitch_dirs)


def _load_timestamp_deltas(paths: Iterable[Path]) -> List[int]:
    deltas: List[int] = []
    for path in paths:
        timestamps: List[int] = []
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    timestamps.append(int(row["t_capture_monotonic_ns"]))
                except (KeyError, ValueError):
                    continue
        for i in range(1, len(timestamps)):
            deltas.append(timestamps[i] - timestamps[i - 1])
    return deltas


def _compute_capture_stats(session_dir: Path, expected_fps: float) -> Dict[str, Dict[str, float]]:
    expected_delta_ns = int(1e9 / expected_fps) if expected_fps > 0 else 0
    stats: Dict[str, Dict[str, float]] = {}
    for label in ("left", "right"):
        paths = list(session_dir.rglob(f"{label}_timestamps.csv"))
        deltas = _load_timestamp_deltas(paths)
        if deltas:
            mean_delta = sum(deltas) / float(len(deltas))
            fps_avg = 1e9 / mean_delta if mean_delta > 0 else 0.0
            fps_inst = 1e9 / deltas[-1] if deltas[-1] > 0 else 0.0
            ref_delta = expected_delta_ns or int(_percentile([d / 1e6 for d in deltas], 50) * 1e6)
            jitter_ms = [abs(d - ref_delta) / 1e6 for d in deltas]
            jitter_p95 = _percentile(jitter_ms, 95)
            drop_thresh = expected_delta_ns * 1.5 if expected_delta_ns else ref_delta * 1.5
            dropped = sum(1 for d in deltas if d > drop_thresh)
        else:
            fps_avg = 0.0
            fps_inst = 0.0
            jitter_p95 = 0.0
            dropped = 0
        stats[label] = {
            "fps_avg": float(fps_avg),
            "fps_inst": float(fps_inst),
            "jitter_p95_ms": float(jitter_p95),
            "dropped_frames": float(dropped),
            "queue_depth": 0.0,
            "capture_latency_ms": 0.0,
        }
    return stats


def _build_detector(config_path: Path, roi_path: Path, camera_id: str):
    config = load_config(config_path)
    cfg = config.detector
    rois = load_rois(roi_path)
    lane = rois.get("lane")
    roi_by_camera = None
    if lane:
        roi_by_camera = {camera_id: [(float(x), float(y)) for x, y in lane]}
    if cfg.type == "ml":
        return MlDetector(
            model_path=cfg.model_path,
            input_size=cfg.model_input_size,
            conf_threshold=cfg.model_conf_threshold,
            class_id=cfg.model_class_id,
            output_format=cfg.model_format,
        )
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
        min_consecutive=cfg.min_consecutive,
    )
    return ClassicalDetector(config=detector_cfg, mode=Mode(cfg.mode), roi_by_camera=roi_by_camera)


def _analyze_videos(
    video_paths: Iterable[Path],
    detector,
    stride: int,
    skip_detection: bool,
    skip_brightness: bool,
    camera_id: str,
    pixfmt: str,
    logs: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    means: List[float] = []
    stds: List[float] = []
    best_confidences: List[float] = []
    radii: List[float] = []
    detections_total = 0
    frame_count = 0

    for path in video_paths:
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            errors.append(
                {
                    "t_utc": None,
                    "level": "error",
                    "message": f"Failed to open video {path}",
                    "context": {"camera": camera_id},
                }
            )
            continue
        logs.append(
            {
                "t_utc": None,
                "level": "info",
                "message": f"Analyzing video {path.name}",
                "context": {"camera": camera_id},
            }
        )
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            if stride > 1 and frame_index % stride != 0:
                continue
            frame_count += 1
            if frame.ndim == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            if not skip_brightness:
                means.append(float(np.mean(gray)))
                stds.append(float(np.std(gray)))
            if skip_detection:
                continue
            try:
                frame_obj = Frame(
                    camera_id=camera_id,
                    frame_index=frame_index,
                    t_capture_monotonic_ns=0,
                    image=gray,
                    width=gray.shape[1],
                    height=gray.shape[0],
                    pixfmt=pixfmt,
                )
                detections = detector.detect(frame_obj)
            except Exception as exc:  # noqa: BLE001 - capture detector failures
                errors.append(
                    {
                        "t_utc": None,
                        "level": "error",
                        "message": f"Detector error: {exc}",
                        "context": {"camera": camera_id},
                    }
                )
                detections = []
            detections_total += len(detections)
            if detections:
                best = max(detections, key=lambda det: det.confidence)
                best_confidences.append(float(best.confidence))
                radii.append(float(best.radius_px))
        capture.release()

    brightness_stats = None
    if not skip_brightness:
        brightness_stats = {
            "frame_count": frame_count,
            "mean_gray_avg": float(sum(means) / len(means)) if means else 0.0,
            "mean_gray_p95": float(_percentile(means, 95)),
            "std_gray_avg": float(sum(stds) / len(stds)) if stds else 0.0,
            "std_gray_p95": float(_percentile(stds, 95)),
        }

    detection_stats = None
    if not skip_detection:
        detection_stats = {
            "frame_count": frame_count,
            "detections_total": int(detections_total),
            "detections_per_frame_avg": float(detections_total / frame_count) if frame_count else 0.0,
            "best_confidence_p95": float(_percentile(best_confidences, 95)),
            "radius_px_avg": float(sum(radii) / len(radii)) if radii else 0.0,
        }

    return brightness_stats, detection_stats


def _build_session_payload(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": summary.get("session_id", "session"),
        "session_name": summary.get("session_name"),
        "started_utc": summary.get("started_utc"),
        "ended_utc": summary.get("ended_utc"),
        "pitch_count": summary.get("pitch_count", 0),
        "strikes": summary.get("strikes", 0),
        "balls": summary.get("balls", 0),
        "heatmap": summary.get("heatmap", [[0, 0, 0], [0, 0, 0], [0, 0, 0]]),
        "pitches": summary.get("pitches", []),
    }


def build_training_report(
    session_dir: Path,
    config_path: Path,
    roi_path: Path,
    stride: int = 1,
    skip_detection: bool = False,
    skip_brightness: bool = False,
    source: Optional[Dict[str, Any]] = None,
    report_id: Optional[str] = None,
    created_utc: Optional[str] = None,
) -> Dict[str, Any]:
    summary_path = session_dir / "session_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing session summary at {summary_path}")
    summary = _load_json(summary_path)
    manifest_path = session_dir / "manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    config = load_config(config_path)

    report_id = report_id or f"training-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}"
    created_utc = created_utc or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    logs: List[Dict[str, Any]] = [
        {
            "t_utc": created_utc,
            "level": "info",
            "message": "Training report generation started.",
            "context": {"session_dir": str(session_dir)},
        }
    ]
    errors: List[Dict[str, Any]] = []

    capture_stats = _compute_capture_stats(session_dir, config.camera.fps)

    brightness_by_camera: Dict[str, Any] = {}
    detection_by_camera: Dict[str, Any] = {}
    for label in ("left", "right"):
        videos = list(session_dir.rglob(f"{label}.avi"))
        detector = None
        if not skip_detection:
            detector = _build_detector(config_path, roi_path, label)
        brightness, detection = _analyze_videos(
            videos,
            detector,
            stride=max(stride, 1),
            skip_detection=skip_detection,
            skip_brightness=skip_brightness,
            camera_id=label,
            pixfmt=config.camera.pixfmt,
            logs=logs,
            errors=errors,
        )
        if brightness is not None:
            brightness_by_camera[label] = brightness
        if detection is not None:
            detection_by_camera[label] = detection

    logs.append(
        {
            "t_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": "info",
            "message": "Training report generation completed.",
            "context": {"errors": len(errors)},
        }
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "report_id": report_id,
        "created_utc": created_utc,
        "session": _build_session_payload(summary),
        "capture_stats": capture_stats,
        "latency_stats": None,
        "brightness_stats": brightness_by_camera if brightness_by_camera else None,
        "detection_stats": detection_by_camera if detection_by_camera else None,
        "noise_metrics": None,
        "errors": errors,
        "logs": logs,
        "recording": {
            "mode": manifest.get("mode"),
            "output_dir": str(session_dir.parent) if session_dir.parent else None,
            "pre_roll_ms": config.recording.pre_roll_ms,
            "post_roll_ms": config.recording.post_roll_ms,
        },
        "files": {
            "session_dir": str(session_dir),
            "manifest": "manifest.json" if manifest_path.exists() else None,
            "session_summary": "session_summary.json",
            "session_summary_csv": "session_summary.csv"
            if (session_dir / "session_summary.csv").exists()
            else None,
        },
        "source": source
        or {
            "app": "PitchTracker",
            "rig_id": None,
            "pitcher": None,
            "location_profile": None,
            "operator": None,
            "host": None,
        },
    }
    return payload


def main() -> None:
    args = parse_args()
    payload = build_training_report(
        session_dir=args.session_dir,
        config_path=args.config,
        roi_path=args.roi,
        stride=args.stride,
        skip_detection=args.skip_detection,
        skip_brightness=args.skip_brightness,
        source={
            "app": "PitchTracker",
            "rig_id": args.rig_id,
            "pitcher": args.pitcher,
            "location_profile": args.location_profile,
            "operator": args.operator,
            "host": args.host,
        },
    )
    out_path = args.out or (args.session_dir / "training_report.json")
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote training report to {out_path}")


if __name__ == "__main__":
    main()
