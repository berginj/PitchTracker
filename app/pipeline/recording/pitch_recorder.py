"""Pitch recording for individual pitch video and pre/post-roll capture."""

from __future__ import annotations

import csv
import json
import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2

from configs.settings import AppConfig
from contracts import Frame
from contracts.versioning import APP_VERSION, SCHEMA_VERSION

logger = logging.getLogger(__name__)


class PitchRecorder:
    """Manages pitch-level video recording with pre-roll and post-roll.

    Records individual pitch videos with pre-roll frames (captured before
    pitch detection) and post-roll frames (captured after pitch ends).
    """

    def __init__(self, config: AppConfig, session_dir: Path, pitch_id: str):
        """Initialize pitch recorder.

        Args:
            config: Application configuration
            session_dir: Session directory containing pitch recordings
            pitch_id: ID of pitch to record
        """
        self._config = config
        self._session_dir = session_dir
        self._pitch_id = pitch_id
        self._pitch_dir = self._create_pitch_dir()

        # Video writers
        self._left_writer: Optional[cv2.VideoWriter] = None
        self._right_writer: Optional[cv2.VideoWriter] = None

        # CSV writers (file handle, csv.writer)
        self._left_csv: Optional[Tuple] = None
        self._right_csv: Optional[Tuple] = None

        # Pre-roll buffers
        pre_roll_ns = int(config.recording.pre_roll_ms * 1e6)
        self._pre_roll_ns = pre_roll_ns
        self._pre_roll_left: deque[Frame] = deque()
        self._pre_roll_right: deque[Frame] = deque()

        # Post-roll tracking
        post_roll_ns = int(config.recording.post_roll_ms * 1e6)
        self._post_roll_ns = post_roll_ns
        self._post_roll_end_ns: Optional[int] = None
        self._latest_ns: Dict[str, int] = {"left": 0, "right": 0}

        # Thread safety
        self._lock = threading.Lock()

    def buffer_pre_roll(self, label: str, frame: Frame) -> None:
        """Buffer frame for pre-roll.

        Maintains a sliding window of frames before pitch detection.

        Args:
            label: Camera label ("left" or "right")
            frame: Frame to buffer
        """
        buffer = self._pre_roll_left if label == "left" else self._pre_roll_right
        buffer.append(frame)

        # Drop frames older than pre-roll window
        cutoff = frame.t_capture_monotonic_ns - self._pre_roll_ns
        while buffer and buffer[0].t_capture_monotonic_ns < cutoff:
            buffer.popleft()

    def start_pitch(self) -> None:
        """Start pitch recording.

        Opens video/CSV writers and flushes pre-roll buffers.
        """
        self._open_writers()
        self._flush_pre_roll()

    def write_frame(self, label: str, frame: Frame) -> None:
        """Write frame to pitch recording.

        Args:
            label: Camera label ("left" or "right")
            frame: Frame to write
        """
        if self._left_writer is None or self._right_writer is None:
            return

        image = frame.image
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        with self._lock:
            if label == "left" and self._left_writer is not None:
                self._left_writer.write(image)
                if self._left_csv is not None:
                    self._left_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
                self._latest_ns["left"] = frame.t_capture_monotonic_ns
            elif label == "right" and self._right_writer is not None:
                self._right_writer.write(image)
                if self._right_csv is not None:
                    self._right_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
                self._latest_ns["right"] = frame.t_capture_monotonic_ns

    def end_pitch(self, end_ns: int) -> None:
        """Mark pitch as ended, continue recording post-roll.

        Args:
            end_ns: Nanosecond timestamp when pitch ended
        """
        self._post_roll_end_ns = end_ns + self._post_roll_ns

    def should_close(self) -> bool:
        """Check if post-roll is complete and recording should close.

        Returns:
            True if both cameras have reached post-roll end time
        """
        if self._post_roll_end_ns is None:
            return False

        left_ns = self._latest_ns.get("left", 0)
        right_ns = self._latest_ns.get("right", 0)
        return left_ns >= self._post_roll_end_ns and right_ns >= self._post_roll_end_ns

    def close(self, force: bool = False) -> None:
        """Close pitch recording.

        Args:
            force: If True, close immediately regardless of post-roll status
        """
        with self._lock:
            if self._left_writer is not None:
                self._left_writer.release()
                self._left_writer = None
            if self._right_writer is not None:
                self._right_writer.release()
                self._right_writer = None
            if self._left_csv is not None:
                self._left_csv[0].close()
                self._left_csv = None
            if self._right_csv is not None:
                self._right_csv[0].close()
                self._right_csv = None
            if force:
                self._post_roll_end_ns = None
                self._latest_ns = {"left": 0, "right": 0}

    def write_manifest(self, summary, config_path: Optional[str]) -> None:
        """Write pitch manifest to JSON file.

        Args:
            summary: PitchSummary object
            config_path: Path to config file used
        """
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "rig_id": None,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pitch_id": summary.pitch_id,
            "t_start_ns": summary.t_start_ns,
            "t_end_ns": summary.t_end_ns,
            "is_strike": summary.is_strike,
            "zone_row": summary.zone_row,
            "zone_col": summary.zone_col,
            "run_in": summary.run_in,
            "rise_in": summary.rise_in,
            "measured_speed_mph": summary.speed_mph,
            "rotation_rpm": summary.rotation_rpm,
            "trajectory": {
                "plate_crossing_xyz_ft": [
                    summary.trajectory_plate_x_ft,
                    summary.trajectory_plate_y_ft,
                    summary.trajectory_plate_z_ft,
                ],
                "plate_crossing_t_ns": summary.trajectory_plate_t_ns,
                "model": summary.trajectory_model,
                "expected_error_ft": summary.trajectory_expected_error_ft,
                "confidence": summary.trajectory_confidence,
            },
            "left_video": "left.avi",
            "right_video": "right.avi",
            "left_timestamps": "left_timestamps.csv",
            "right_timestamps": "right_timestamps.csv",
            "config_path": config_path or "configs/default.yaml",
        }
        (self._pitch_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    def is_active(self) -> bool:
        """Check if pitch recording is active.

        Returns:
            True if recording, False otherwise
        """
        return self._left_writer is not None and self._right_writer is not None

    def get_pitch_dir(self) -> Path:
        """Get pitch directory.

        Returns:
            Path to pitch directory
        """
        return self._pitch_dir

    def _create_pitch_dir(self) -> Path:
        """Create pitch directory.

        Returns:
            Path to pitch directory
        """
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in self._pitch_id)
        pitch_dir = self._session_dir / safe
        pitch_dir.mkdir(parents=True, exist_ok=True)
        return pitch_dir

    def _open_writers(self) -> None:
        """Open video writers and CSV files."""
        left_path = self._pitch_dir / "left.avi"
        right_path = self._pitch_dir / "right.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")

        self._left_writer = cv2.VideoWriter(
            str(left_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        self._right_writer = cv2.VideoWriter(
            str(right_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )

        # Open CSV files
        left_csv = (self._pitch_dir / "left_timestamps.csv").open("w", newline="")
        right_csv = (self._pitch_dir / "right_timestamps.csv").open("w", newline="")
        self._left_csv = (left_csv, csv.writer(left_csv))
        self._right_csv = (right_csv, csv.writer(right_csv))

        # Write CSV headers
        self._left_csv[1].writerow(["camera_id", "frame_index", "t_capture_monotonic_ns"])
        self._right_csv[1].writerow(["camera_id", "frame_index", "t_capture_monotonic_ns"])

        # Reset tracking
        self._post_roll_end_ns = None
        self._latest_ns = {"left": 0, "right": 0}

    def _flush_pre_roll(self) -> None:
        """Flush pre-roll buffers to pitch recording."""
        for frame in list(self._pre_roll_left):
            self.write_frame("left", frame)
        for frame in list(self._pre_roll_right):
            self.write_frame("right", frame)
