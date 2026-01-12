"""Dual-camera UVC capture and recording utility for Windows."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from threading import Thread

import cv2

from capture.uvc_backend import UvcCamera
from configs.settings import load_config
from contracts.versioning import APP_VERSION, SCHEMA_VERSION


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record dual UVC cameras to disk.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--left-serial", required=True, help="Left camera serial number.")
    parser.add_argument("--right-serial", required=True, help="Right camera serial number.")
    parser.add_argument("--out-dir", type=Path, default=Path("recordings"))
    parser.add_argument("--duration", type=float, default=5.0, help="Seconds to record.")
    parser.add_argument("--codec", default="MJPG", help="FourCC codec (default MJPG).")
    parser.add_argument("--pitch-id", default=None, help="Optional pitch identifier.")
    parser.add_argument("--rig-id", default=None, help="Optional rig identifier.")
    parser.add_argument(
        "--calibration-profile-id",
        default=None,
        help="Optional calibration profile identifier.",
    )
    return parser.parse_args()


def _open_writer(
    path: Path, width: int, height: int, fps: int, codec: str
) -> cv2.VideoWriter:
    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height), True)
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter for {path}.")
    return writer


def _capture_loop(
    label: str,
    camera: UvcCamera,
    writer: cv2.VideoWriter,
    csv_path: Path,
    end_time: float,
) -> None:
    with csv_path.open("w", newline="") as handle:
        csv_writer = csv.writer(handle)
        csv_writer.writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        while time.monotonic() < end_time:
            frame = camera.read_frame(timeout_ms=200)
            image = frame.image
            if image.ndim == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            writer.write(image)
            csv_writer.writerow(
                [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
            )
    writer.release()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    created_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    pitch_id = args.pitch_id or time.strftime("pitch-%Y%m%d-%H%M%S", time.gmtime())

    left = UvcCamera()
    right = UvcCamera()
    left.open(args.left_serial)
    right.open(args.right_serial)
    left.set_mode(
        config.camera.width,
        config.camera.height,
        config.camera.fps,
        config.camera.pixfmt,
    )
    right.set_mode(
        config.camera.width,
        config.camera.height,
        config.camera.fps,
        config.camera.pixfmt,
    )
    left.set_controls(
        config.camera.exposure_us,
        config.camera.gain,
        config.camera.wb_mode,
        config.camera.wb,
    )
    right.set_controls(
        config.camera.exposure_us,
        config.camera.gain,
        config.camera.wb_mode,
        config.camera.wb,
    )

    left_video = args.out_dir / "left.avi"
    right_video = args.out_dir / "right.avi"
    left_csv = args.out_dir / "left_timestamps.csv"
    right_csv = args.out_dir / "right_timestamps.csv"
    manifest_path = args.out_dir / "manifest.json"

    left_writer = _open_writer(
        left_video, config.camera.width, config.camera.height, config.camera.fps, args.codec
    )
    right_writer = _open_writer(
        right_video,
        config.camera.width,
        config.camera.height,
        config.camera.fps,
        args.codec,
    )

    end_time = time.monotonic() + args.duration
    left_thread = Thread(
        target=_capture_loop,
        args=("left", left, left_writer, left_csv, end_time),
        daemon=True,
    )
    right_thread = Thread(
        target=_capture_loop,
        args=("right", right, right_writer, right_csv, end_time),
        daemon=True,
    )

    left_thread.start()
    right_thread.start()
    left_thread.join()
    right_thread.join()

    left_stats = left.get_stats()
    right_stats = right.get_stats()
    left.close()
    right.close()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "rig_id": args.rig_id,
        "created_utc": created_utc,
        "pitch_id": pitch_id,
        "left_video": left_video.name,
        "right_video": right_video.name,
        "left_timestamps": left_csv.name,
        "right_timestamps": right_csv.name,
        "config_path": str(args.config),
        "calibration_profile_id": args.calibration_profile_id,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(
        "left stats fps_avg={:.2f} fps_inst={:.2f} jitter_p95_ms={:.2f} dropped={}".format(
            left_stats.fps_avg,
            left_stats.fps_instant,
            left_stats.jitter_p95_ms,
            left_stats.dropped_frames,
        )
    )
    print(
        "right stats fps_avg={:.2f} fps_inst={:.2f} jitter_p95_ms={:.2f} dropped={}".format(
            right_stats.fps_avg,
            right_stats.fps_instant,
            right_stats.jitter_p95_ms,
            right_stats.dropped_frames,
        )
    )


if __name__ == "__main__":
    main()
