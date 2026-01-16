"""Session recording for full session video and timestamp capture."""

from __future__ import annotations

import csv
import json
import logging
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Tuple

import cv2

from configs.settings import AppConfig
from contracts import Frame
from contracts.versioning import APP_VERSION, SCHEMA_VERSION

from app.pipeline.recording.manifest import create_session_manifest

logger = logging.getLogger(__name__)


class SessionRecorder:
    """Manages session-level video recording and timestamp logging.

    Records full session video for both cameras with frame timestamps,
    and writes session summary at the end.
    """

    def __init__(self, config: AppConfig, record_dir: Optional[Path] = None):
        """Initialize session recorder.

        Args:
            config: Application configuration
            record_dir: Base directory for recordings
        """
        self._config = config
        self._record_dir = record_dir or Path("recordings")
        self._session_dir: Optional[Path] = None

        # Video writers
        self._left_writer: Optional[cv2.VideoWriter] = None
        self._right_writer: Optional[cv2.VideoWriter] = None

        # CSV writers (file handle, csv.writer)
        self._left_csv: Optional[Tuple] = None
        self._right_csv: Optional[Tuple] = None

        # Thread safety
        self._lock = threading.Lock()

    def start_session(self, session_name: str, pitch_id: str) -> Path:
        """Start session recording.

        Creates session directory and opens video/CSV writers.

        Args:
            session_name: Name of session
            pitch_id: Initial pitch ID (used if session_name is None)

        Returns:
            Path to session directory
        """
        base = session_name or pitch_id
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in base)
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        self._session_dir = self._record_dir / f"{safe}_{timestamp}"
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._open_writers()
        return self._session_dir

    def stop_session(
        self,
        config_path: Optional[str],
        pitch_id: str,
        session_name: Optional[str],
        mode: Optional[str],
        measured_speed_mph: Optional[float],
    ) -> None:
        """Stop session recording.

        Closes video/CSV writers and writes manifest.

        Args:
            config_path: Path to config file used
            pitch_id: Last pitch ID
            session_name: Session name
            mode: Recording mode
            measured_speed_mph: Manual speed measurement
        """
        self._close_writers()

        if self._session_dir is None:
            return

        # Write manifest
        manifest = create_session_manifest(
            pitch_id=pitch_id,
            session_name=session_name,
            mode=mode,
            measured_speed_mph=measured_speed_mph,
            config_path=config_path,
        )
        (self._session_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    def write_frame(self, label: str, frame: Frame) -> None:
        """Write frame to session recording.

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
            elif label == "right" and self._right_writer is not None:
                self._right_writer.write(image)
                if self._right_csv is not None:
                    self._right_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )

    def write_session_summary(self, summary) -> None:
        """Write session summary to JSON and CSV files.

        Args:
            summary: SessionSummary object
        """
        if self._session_dir is None:
            return

        # Write JSON
        path = self._session_dir / "session_summary.json"
        payload = asdict(summary)
        payload["schema_version"] = SCHEMA_VERSION
        payload["app_version"] = APP_VERSION
        path.write_text(json.dumps(payload, indent=2))

        # Write CSV
        self._write_session_summary_csv(summary)

    def get_session_dir(self) -> Optional[Path]:
        """Get current session directory.

        Returns:
            Path to session directory, or None if not recording
        """
        return self._session_dir

    def is_active(self) -> bool:
        """Check if session recording is active.

        Returns:
            True if recording, False otherwise
        """
        return self._left_writer is not None and self._right_writer is not None

    def _open_writers(self) -> None:
        """Open video writers and CSV files."""
        if self._session_dir is None:
            return

        left_path = self._session_dir / "session_left.avi"
        right_path = self._session_dir / "session_right.avi"
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
        left_csv = (self._session_dir / "session_left_timestamps.csv").open("w", newline="")
        right_csv = (self._session_dir / "session_right_timestamps.csv").open("w", newline="")
        self._left_csv = (left_csv, csv.writer(left_csv))
        self._right_csv = (right_csv, csv.writer(right_csv))

        # Write CSV headers
        self._left_csv[1].writerow(["camera_id", "frame_index", "t_capture_monotonic_ns"])
        self._right_csv[1].writerow(["camera_id", "frame_index", "t_capture_monotonic_ns"])

    def _close_writers(self) -> None:
        """Close video writers and CSV files."""
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

    def _write_session_summary_csv(self, summary) -> None:
        """Write session summary to CSV file.

        Args:
            summary: SessionSummary object
        """
        if self._session_dir is None:
            return

        path = self._session_dir / "session_summary.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "pitch_id",
                    "t_start_ns",
                    "t_end_ns",
                    "is_strike",
                    "zone_row",
                    "zone_col",
                    "run_in",
                    "rise_in",
                    "speed_mph",
                    "rotation_rpm",
                    "sample_count",
                    "trajectory_plate_x_ft",
                    "trajectory_plate_y_ft",
                    "trajectory_plate_z_ft",
                    "trajectory_plate_t_ns",
                    "trajectory_model",
                    "trajectory_expected_error_ft",
                    "trajectory_confidence",
                ]
            )
            for pitch in summary.pitches:
                writer.writerow(
                    [
                        pitch.pitch_id,
                        pitch.t_start_ns,
                        pitch.t_end_ns,
                        int(pitch.is_strike),
                        pitch.zone_row if pitch.zone_row is not None else "",
                        pitch.zone_col if pitch.zone_col is not None else "",
                        f"{pitch.run_in:.3f}",
                        f"{pitch.rise_in:.3f}",
                        f"{pitch.speed_mph:.3f}" if pitch.speed_mph is not None else "",
                        f"{pitch.rotation_rpm:.3f}" if pitch.rotation_rpm is not None else "",
                        pitch.sample_count,
                        f"{pitch.trajectory_plate_x_ft:.4f}" if pitch.trajectory_plate_x_ft is not None else "",
                        f"{pitch.trajectory_plate_y_ft:.4f}" if pitch.trajectory_plate_y_ft is not None else "",
                        f"{pitch.trajectory_plate_z_ft:.4f}" if pitch.trajectory_plate_z_ft is not None else "",
                        pitch.trajectory_plate_t_ns if pitch.trajectory_plate_t_ns is not None else "",
                        pitch.trajectory_model if pitch.trajectory_model is not None else "",
                        f"{pitch.trajectory_expected_error_ft:.4f}"
                        if pitch.trajectory_expected_error_ft is not None
                        else "",
                        f"{pitch.trajectory_confidence:.3f}" if pitch.trajectory_confidence is not None else "",
                    ]
                )
