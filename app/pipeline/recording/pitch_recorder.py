"""Pitch recording for individual pitch video and pre/post-roll capture."""

from __future__ import annotations

import csv
import json
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2

from configs.settings import AppConfig
from contracts import Frame, Detection, StereoObservation

from app.pipeline.recording.manifest import create_pitch_manifest
from app.pipeline.recording.frame_extractor import FrameExtractor

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

        # Calculate max frames for pre-roll based on config (with 20% safety margin)
        max_pre_roll_frames = int(config.recording.pre_roll_ms * config.camera.fps / 1000 * 1.2)
        self._pre_roll_left: deque[Frame] = deque(maxlen=max_pre_roll_frames)
        self._pre_roll_right: deque[Frame] = deque(maxlen=max_pre_roll_frames)

        # Post-roll tracking
        post_roll_ns = int(config.recording.post_roll_ms * 1e6)
        self._post_roll_ns = post_roll_ns
        self._post_roll_end_ns: Optional[int] = None
        self._latest_ns: Dict[str, int] = {"left": 0, "right": 0}

        # ML training data: Detection storage
        self._save_detections = getattr(config.recording, "save_detections", False)
        self._detections: Dict[str, List[Dict]] = {"left": [], "right": []}
        self._detection_count: Dict[str, int] = {"left": 0, "right": 0}

        # ML training data: Observation storage
        self._save_observations = getattr(config.recording, "save_observations", False)
        self._observations: List[Dict] = []

        # ML training data: Frame extraction
        self._save_frames = getattr(config.recording, "save_training_frames", False)
        self._frame_extractor = FrameExtractor(self._pitch_dir, enabled=self._save_frames)
        self._frame_interval = getattr(config.recording, "frame_save_interval", 5)

        # Track pitch phase for keypoint extraction
        self._pitch_started = False
        self._pitch_ended = False

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
        self._pitch_started = True

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

    def write_frame_with_detections(
        self, label: str, frame: Frame, detections: Optional[List[Detection]] = None
    ) -> None:
        """Write frame and optionally store detection data.

        Args:
            label: Camera label ("left" or "right")
            frame: Frame to write
            detections: Optional list of detections in this frame
        """
        # Write video frame (existing)
        self.write_frame(label, frame)

        # Store detection data for ML training
        if self._save_detections and detections:
            for det in detections:
                self._detections[label].append({
                    "frame_index": frame.frame_index,
                    "timestamp_ns": det.t_capture_monotonic_ns,
                    "u_px": float(det.u),
                    "v_px": float(det.v),
                    "radius_px": float(det.radius_px),
                    "confidence": float(det.confidence),
                })
                self._detection_count[label] += 1

        # Extract frames for ML training
        if self._save_frames:
            # Save first pre-roll frame
            if not self._pitch_started:
                self._frame_extractor.save_pre_roll_first(label, frame)

            # Save first detection frame
            if self._pitch_started and detections and len(detections) > 0:
                self._frame_extractor.save_first_detection(label, frame)

            # Save uniform intervals
            self._frame_extractor.save_uniform(label, frame, self._frame_interval)

            # Save last detection (continuously updated)
            if detections and len(detections) > 0:
                self._frame_extractor.save_last_detection(label, frame)

            # Save post-roll last frame
            if self._pitch_ended:
                self._frame_extractor.save_post_roll_last(label, frame)

    def add_observation(self, obs: StereoObservation) -> None:
        """Store stereo observation for export.

        Args:
            obs: Stereo observation to store
        """
        if self._save_observations:
            self._observations.append({
                "timestamp_ns": obs.t_ns,
                "left_px": [float(obs.left[0]), float(obs.left[1])],
                "right_px": [float(obs.right[0]), float(obs.right[1])],
                "X_ft": float(obs.X),
                "Y_ft": float(obs.Y),
                "Z_ft": float(obs.Z),
                "quality": float(obs.quality),
                "confidence": float(obs.confidence),
            })

    def end_pitch(self, end_ns: int) -> None:
        """Mark pitch as ended, continue recording post-roll.

        Args:
            end_ns: Nanosecond timestamp when pitch ended
        """
        self._post_roll_end_ns = end_ns + self._post_roll_ns
        self._pitch_ended = True

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

        # Export ML training data (outside lock)
        if self._save_detections and (
            self._detection_count["left"] > 0 or self._detection_count["right"] > 0
        ):
            self._export_detections()

        if self._save_observations and self._observations:
            self._export_observations()

    def write_manifest(
        self, summary, config_path: Optional[str], performance_metrics: Optional[Dict] = None
    ) -> None:
        """Write pitch manifest to JSON file.

        Args:
            summary: PitchSummary object
            config_path: Path to config file used
            performance_metrics: Optional performance metrics dict
        """
        manifest = create_pitch_manifest(summary, config_path, performance_metrics)
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
        # Try H.264 first (better compression, hardware acceleration if available)
        # Fall back to MJPEG if H.264 not supported
        codec_options = [
            ("H264", ".mp4"),   # H.264 codec - 5-10x better compression
            ("avc1", ".mp4"),   # Alternative H.264 fourcc
            ("MJPG", ".avi"),   # Fallback to MJPEG
        ]

        fourcc = None
        extension = None
        for codec, ext in codec_options:
            test_fourcc = cv2.VideoWriter_fourcc(*codec)
            # Test if codec is supported by trying to open a writer
            test_writer = cv2.VideoWriter(
                "test.tmp",
                test_fourcc,
                self._config.camera.fps,
                (self._config.camera.width, self._config.camera.height),
                True,
            )
            if test_writer.isOpened():
                fourcc = test_fourcc
                extension = ext
                test_writer.release()
                import os
                if os.path.exists("test.tmp"):
                    os.remove("test.tmp")
                logger.info(f"Using video codec: {codec} (extension: {extension})")
                break
            test_writer.release()

        if fourcc is None:
            logger.warning("No supported video codec found, defaulting to MJPEG")
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            extension = ".avi"

        left_path = self._pitch_dir / f"left{extension}"
        right_path = self._pitch_dir / f"right{extension}"

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

    def _export_detections(self) -> None:
        """Export detection data to JSON files."""
        detections_dir = self._pitch_dir / "detections"
        detections_dir.mkdir(exist_ok=True)

        for camera in ["left", "right"]:
            if self._detections[camera]:
                detection_file = detections_dir / f"{camera}_detections.json"
                data = {
                    "pitch_id": self._pitch_id,
                    "camera": camera,
                    "detection_count": self._detection_count[camera],
                    "detections": self._detections[camera],
                }
                detection_file.write_text(json.dumps(data, indent=2))
                logger.info(
                    f"Exported {self._detection_count[camera]} detections to {detection_file}"
                )

    def _export_observations(self) -> None:
        """Export stereo observations to JSON file."""
        obs_dir = self._pitch_dir / "observations"
        obs_dir.mkdir(exist_ok=True)

        obs_file = obs_dir / "stereo_observations.json"
        data = {
            "pitch_id": self._pitch_id,
            "observation_count": len(self._observations),
            "observations": self._observations,
        }
        obs_file.write_text(json.dumps(data, indent=2))
        logger.info(f"Exported {len(self._observations)} observations to {obs_file}")
