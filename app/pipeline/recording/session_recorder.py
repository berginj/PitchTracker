"""Session recording for full session video and timestamp capture."""

from __future__ import annotations

import csv
import json
import logging
import shutil
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Tuple

import cv2

from app.events import ErrorCategory, ErrorSeverity, publish_error
from app.pipeline.recording.manifest import create_session_manifest
from configs.settings import AppConfig
from contracts import Frame
from contracts.versioning import APP_VERSION, SCHEMA_VERSION

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

        # Track write failures
        self._write_failures = 0
        self._last_write_warning = 0.0

        # Disk space monitoring
        self._disk_monitor_thread: Optional[threading.Thread] = None
        self._monitoring_disk = False
        self._disk_error_callback: Optional[callable] = None
        self._critical_disk_gb = 5.0  # Stop recording if below this
        self._warning_disk_gb = 20.0  # Warn user if below this

    def _check_disk_space(self, required_gb: float = 50.0) -> tuple[bool, str]:
        """Check disk space and return warning message if low.

        Args:
            required_gb: Recommended free space in GB

        Returns:
            Tuple of (has_enough_space, warning_message)
            - has_enough_space: True if >= required_gb, False otherwise
            - warning_message: Empty if enough space, warning text otherwise
        """
        usage = shutil.disk_usage(self._record_dir)
        free_gb = usage.free / (1024**3)

        logger.info(f"Disk space check: {free_gb:.1f}GB available on {self._record_dir}")

        if free_gb < required_gb:
            message = (
                f"Low disk space warning!\n\n"
                f"Available: {free_gb:.1f}GB\n"
                f"Recommended: {required_gb}GB\n\n"
                f"Recording may fail if disk fills up during session."
            )
            logger.warning(f"Low disk space: {free_gb:.1f}GB available (recommended: {required_gb}GB)")
            return False, message

        # Warn if less than 2x required (< 100GB for 100 pitches)
        if free_gb < required_gb * 2:
            logger.warning(
                f"Moderate disk space: {free_gb:.1f}GB available. "
                f"Recommended: {required_gb * 2:.0f}GB for safety."
            )

        return True, ""

    def set_disk_error_callback(self, callback: callable) -> None:
        """Set callback for disk space emergencies.

        Args:
            callback: Function to call when disk space critical, receives (free_gb, message)
        """
        self._disk_error_callback = callback

    def _monitor_disk_space(self) -> None:
        """Background thread to monitor disk space during recording.

        Checks disk space every 5 seconds. Triggers emergency stop if critical.
        """
        last_warning_time = 0.0

        while self._monitoring_disk:
            try:
                usage = shutil.disk_usage(self._record_dir)
                free_gb = usage.free / (1024**3)

                current_time = time.time()

                # Critical level - trigger emergency callback
                if free_gb < self._critical_disk_gb:
                    logger.critical(
                        f"CRITICAL DISK SPACE: {free_gb:.1f}GB remaining! "
                        f"Recording must stop immediately to avoid data corruption."
                    )

                    # Publish critical error event
                    publish_error(
                        category=ErrorCategory.DISK_SPACE,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"Critical disk space: {free_gb:.1f}GB remaining",
                        source="SessionRecorder.disk_monitor",
                        free_gb=free_gb,
                        threshold_gb=self._critical_disk_gb,
                    )

                    if self._disk_error_callback:
                        try:
                            self._disk_error_callback(
                                free_gb,
                                f"Critical: Only {free_gb:.1f}GB disk space remaining!"
                            )
                        except Exception as e:
                            logger.error(f"Disk error callback failed: {e}")
                    # Stop monitoring - callback should stop recording
                    break

                # Warning level - log periodically
                elif free_gb < self._warning_disk_gb:
                    # Throttle warnings to once per minute
                    if current_time - last_warning_time > 60.0:
                        logger.warning(
                            f"Low disk space: {free_gb:.1f}GB remaining. "
                            f"Consider ending session soon."
                        )
                        last_warning_time = current_time

                        # Publish warning event
                        publish_error(
                            category=ErrorCategory.DISK_SPACE,
                            severity=ErrorSeverity.WARNING,
                            message=f"Low disk space: {free_gb:.1f}GB remaining",
                            source="SessionRecorder.disk_monitor",
                            free_gb=free_gb,
                            threshold_gb=self._warning_disk_gb,
                        )

                # Check every 5 seconds
                time.sleep(5.0)

            except Exception as e:
                logger.error(f"Error monitoring disk space: {e}")
                time.sleep(5.0)  # Continue monitoring despite error

        logger.info("Disk space monitoring stopped")

    def start_session(self, session_name: str, pitch_id: str) -> tuple[Path, str]:
        """Start session recording.

        Creates session directory and opens video/CSV writers.

        Args:
            session_name: Name of session
            pitch_id: Initial pitch ID (used if session_name is None)

        Returns:
            Tuple of (session_dir, warning_message)
            - session_dir: Path to session directory
            - warning_message: Disk space warning if low, empty string otherwise
        """
        # Check disk space before starting (warning, not blocker)
        has_space, warning = self._check_disk_space(required_gb=50.0)

        base = session_name or pitch_id
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in base)
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        self._session_dir = self._record_dir / f"{safe}_{timestamp}"
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._open_writers()

        # Start background disk space monitoring
        self._monitoring_disk = True
        self._disk_monitor_thread = threading.Thread(
            target=self._monitor_disk_space,
            name="DiskSpaceMonitor",
            daemon=False  # Non-daemon so we can join cleanly
        )
        self._disk_monitor_thread.start()
        logger.info("Started disk space monitoring thread")

        logger.info(f"✓ Session recording started: {self._session_dir}")
        return self._session_dir, warning

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
        # Stop disk space monitoring thread
        self._monitoring_disk = False
        if self._disk_monitor_thread is not None and self._disk_monitor_thread.is_alive():
            logger.info("Stopping disk space monitoring...")
            self._disk_monitor_thread.join(timeout=2.0)
            if self._disk_monitor_thread.is_alive():
                logger.warning("Disk monitor thread did not stop cleanly")
            self._disk_monitor_thread = None

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
        """Write frame to session recording with error detection.

        Args:
            label: Camera label ("left" or "right")
            frame: Frame to write

        Logs errors if video write fails (e.g., disk full).
        """
        if self._left_writer is None or self._right_writer is None:
            return

        image = frame.image
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        with self._lock:
            if label == "left" and self._left_writer is not None:
                # Write frame and check for failure
                success = self._left_writer.write(image)
                if not success:
                    self._write_failures += 1
                    # Throttle warnings (don't spam logs)
                    current_time = time.monotonic()
                    if current_time - self._last_write_warning > 5.0:
                        logger.error(
                            f"⚠️ Video write FAILED: LEFT camera, frame {frame.frame_index}\n"
                            f"   Possible causes: Disk full, codec error, I/O error\n"
                            f"   Total failures: {self._write_failures}"
                        )
                        self._last_write_warning = current_time

                        # Publish error event
                        severity = ErrorSeverity.CRITICAL if self._write_failures >= 10 else ErrorSeverity.ERROR
                        publish_error(
                            category=ErrorCategory.RECORDING,
                            severity=severity,
                            message=f"Video write failed for LEFT camera (frame {frame.frame_index})",
                            source="SessionRecorder.write_frame",
                            camera="left",
                            frame_index=frame.frame_index,
                            total_failures=self._write_failures,
                        )

                # Write CSV timestamp regardless
                if self._left_csv is not None:
                    self._left_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )

            elif label == "right" and self._right_writer is not None:
                # Write frame and check for failure
                success = self._right_writer.write(image)
                if not success:
                    self._write_failures += 1
                    # Throttle warnings (don't spam logs)
                    current_time = time.monotonic()
                    if current_time - self._last_write_warning > 5.0:
                        logger.error(
                            f"⚠️ Video write FAILED: RIGHT camera, frame {frame.frame_index}\n"
                            f"   Possible causes: Disk full, codec error, I/O error\n"
                            f"   Total failures: {self._write_failures}"
                        )
                        self._last_write_warning = current_time

                        # Publish error event
                        severity = ErrorSeverity.CRITICAL if self._write_failures >= 10 else ErrorSeverity.ERROR
                        publish_error(
                            category=ErrorCategory.RECORDING,
                            severity=severity,
                            message=f"Video write failed for RIGHT camera (frame {frame.frame_index})",
                            source="SessionRecorder.write_frame",
                            camera="right",
                            frame_index=frame.frame_index,
                            total_failures=self._write_failures,
                        )

                # Write CSV timestamp regardless
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

    def _open_video_writer(self, path: Path, width: int, height: int, fps: int) -> cv2.VideoWriter:
        """Open video writer with codec fallback.

        Args:
            path: Output video file path
            width: Frame width
            height: Frame height
            fps: Frames per second

        Returns:
            Opened VideoWriter

        Raises:
            RuntimeError: If no codec works
        """
        # Try codecs in order of preference
        codec_list = ["MJPG", "XVID", "H264", "MP4V"]

        for codec_name in codec_list:
            fourcc = cv2.VideoWriter_fourcc(*codec_name)
            writer = cv2.VideoWriter(
                str(path),
                fourcc,
                float(fps),
                (width, height),
                True
            )

            if writer.isOpened():
                logger.info(f"Video writer opened successfully: {path.name} with {codec_name} codec")
                return writer
            else:
                # Clean up failed attempt
                writer.release()
                logger.debug(f"Codec {codec_name} failed for {path.name}, trying next...")

        # All codecs failed - publish error event
        error_msg = (
            f"Failed to open video writer for {path.name}. "
            f"Tried codecs: {codec_list}. Check that ffmpeg or system codecs are installed."
        )

        publish_error(
            category=ErrorCategory.RECORDING,
            severity=ErrorSeverity.CRITICAL,
            message=f"All video codecs failed for {path.name}",
            source="SessionRecorder._open_video_writer",
            video_path=str(path),
            tried_codecs=codec_list,
        )

        raise RuntimeError(error_msg)

    def _open_writers(self) -> None:
        """Open video writers and CSV files."""
        if self._session_dir is None:
            return

        left_path = self._session_dir / "session_left.avi"
        right_path = self._session_dir / "session_right.avi"

        width = self._config.camera.width
        height = self._config.camera.height
        fps = self._config.camera.fps

        # Open video writers with codec fallback
        try:
            self._left_writer = self._open_video_writer(left_path, width, height, fps)
        except RuntimeError as e:
            logger.error(f"Failed to open left video writer: {e}")
            raise

        try:
            self._right_writer = self._open_video_writer(right_path, width, height, fps)
        except RuntimeError as e:
            logger.error(f"Failed to open right video writer: {e}")
            # Clean up left writer if right fails
            if self._left_writer:
                self._left_writer.release()
                self._left_writer = None
            raise

        logger.info(f"Session recording initialized: {width}x{height}@{fps}fps")

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
