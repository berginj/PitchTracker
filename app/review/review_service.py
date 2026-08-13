"""Review service for managing session playback and analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

from configs.settings import DetectorConfig
from app.review.review_detection import (
    build_detectors,
    default_detector_config,
    detect_frame,
    detector_config_dict,
    update_detector_config as updated_detector_config,
)
from app.review.session_loader import LoadedSession, SessionLoader
from app.review.video_reader import VideoReader
from detect.classical_detector import ClassicalDetector
from detect.config import Mode
from log_config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Annotation:
    """Manual annotation for a review frame."""

    frame_index: int
    camera: str
    x: float
    y: float
    annotation_type: str = "manual"
    confidence: float = 1.0
    note: Optional[str] = None


class PitchScore(Enum):
    """Quality score for pitch detection."""

    GOOD = "good"
    PARTIAL = "partial"
    MISSED = "missed"
    UNSCORED = "unscored"


class ReviewService:
    """Manage session loading, playback, re-detection, and review exports."""

    def __init__(self) -> None:
        self._session: Optional[LoadedSession] = None
        self._video_reader = VideoReader()
        self._detector_config: Optional[DetectorConfig] = None
        self._detector_mode = Mode.MODE_A
        self._detector_left: Optional[ClassicalDetector] = None
        self._detector_right: Optional[ClassicalDetector] = None
        self._annotations: dict[int, list[Annotation]] = {}
        self._pitch_scores: dict[str, PitchScore] = {}
        self._playback_speed = 1.0
        logger.debug("ReviewService initialized")

    def load_session(self, session_dir: Path) -> LoadedSession:
        """Load a session, open its paired videos, and reset review state."""
        logger.info(f"Loading session for review: {session_dir}")
        session = SessionLoader.load_session(session_dir)
        self._session = session
        if not session.left_video_path.exists():
            raise FileNotFoundError(f"Left video not found: {session.left_video_path}")
        if not session.right_video_path.exists():
            raise FileNotFoundError(f"Right video not found: {session.right_video_path}")
        self._video_reader.open_videos(session.left_video_path, session.right_video_path)
        self._set_session_detector_config(session)
        self._pitch_scores = {pitch.pitch_id: PitchScore.UNSCORED for pitch in session.pitches}
        self._annotations.clear()
        logger.info(
            f"Session loaded: {session.session_id}, {len(session.pitches)} pitches, "
            f"{self._video_reader.total_frames} frames"
        )
        return session

    def _set_session_detector_config(self, session: LoadedSession) -> None:
        if session.original_config:
            self._detector_config = session.original_config.detector
            self._detector_mode = Mode(session.original_config.detector.mode)
            logger.info("Loaded original detector configuration")
        else:
            self._detector_config = default_detector_config()
            self._detector_mode = Mode.MODE_A
            logger.info("Using default detector configuration")
        self._detector_left = None
        self._detector_right = None

    def get_current_frames(
        self,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Read the paired frames at the current reader position."""
        return self._video_reader.read_frames()

    def seek_to_frame(self, frame_index: int) -> bool:
        """Seek to a zero-based paired frame."""
        return self._video_reader.seek_to_frame(frame_index)

    def seek_to_pitch(self, pitch_index: int) -> bool:
        """Seek to the existing approximate frame for a pitch index."""
        if not self._session or pitch_index < 0 or pitch_index >= len(self._session.pitches):
            logger.warning(f"Invalid pitch index: {pitch_index}")
            return False
        pitch = self._session.pitches[pitch_index]
        logger.info(f"Seeking to pitch {pitch.pitch_id}")
        return self.seek_to_frame(pitch_index * 100)

    def step_forward(self, num_frames: int = 1) -> bool:
        """Step the paired reader forward."""
        return self._video_reader.step_forward(num_frames)

    def step_backward(self, num_frames: int = 1) -> bool:
        """Step the paired reader backward."""
        return self._video_reader.step_backward(num_frames)

    def seek_to_start(self) -> bool:
        """Seek to the first paired frame."""
        return self._video_reader.seek_to_start()

    def seek_to_end(self) -> bool:
        """Seek to the last paired frame."""
        return self._video_reader.seek_to_end()

    def update_detector_config(
        self,
        frame_diff_threshold: Optional[float] = None,
        bg_diff_threshold: Optional[float] = None,
        min_area: Optional[int] = None,
        max_area: Optional[int] = None,
        min_circularity: Optional[float] = None,
        mode: Optional[Mode] = None,
    ) -> None:
        """Update supported frozen detector settings and rebuild lazily."""
        if not self._detector_config:
            logger.warning("No detector config loaded")
            return
        self._detector_config = updated_detector_config(
            self._detector_config,
            frame_diff_threshold=frame_diff_threshold,
            bg_diff_threshold=bg_diff_threshold,
            min_area=min_area,
            max_area=max_area,
            min_circularity=min_circularity,
            mode=mode,
        )
        if mode is not None:
            self._detector_mode = mode
        self._rebuild_detectors()
        logger.debug(f"Updated detector config: {self._detector_config}")

    def _rebuild_detectors(self) -> None:
        if not self._detector_config:
            return
        self._detector_left, self._detector_right = build_detectors(self._detector_config, self._detector_mode)
        logger.debug("Rebuilt detectors with updated config")

    def run_detection_on_current_frame(self) -> tuple[list, list]:
        """Run independent detection on the current left and right frames."""
        if not self._detector_left or not self._detector_right:
            self._rebuild_detectors()
        left_frame, right_frame = self.get_current_frames()
        frame_index = self._video_reader.current_frame_index
        return (
            detect_frame(self._detector_left, left_frame, "left", frame_index),
            detect_frame(self._detector_right, right_frame, "right", frame_index),
        )

    def add_annotation(
        self,
        frame_index: int,
        camera: str,
        x: float,
        y: float,
        note: str = "",
    ) -> None:
        """Add a manual annotation to a frame."""
        annotation = Annotation(
            frame_index=frame_index,
            camera=camera,
            x=x,
            y=y,
            note=note or None,
        )
        self._annotations.setdefault(frame_index, []).append(annotation)
        logger.info(f"Added annotation at frame {frame_index}, {camera} ({x:.1f}, {y:.1f})")

    def score_pitch(self, pitch_id: str, score: PitchScore) -> None:
        """Record a pitch detection-quality score."""
        self._pitch_scores[pitch_id] = score
        logger.info(f"Scored pitch {pitch_id}: {score.value}")

    def export_config(self, output_path: Path) -> None:
        """Export the current detector configuration as JSON."""
        if not self._detector_config:
            logger.warning("No detector config to export")
            return
        output_json = output_path.with_suffix(".json")
        with output_json.open("w") as handle:
            json.dump(detector_config_dict(self._detector_config), handle, indent=2)
        logger.info(f"Exported detector config to {output_json}")

    def export_annotations(self, output_path: Path) -> None:
        """Export annotations and pitch scores as JSON."""
        annotations = [
            asdict(annotation)
            for _, frame_annotations in sorted(self._annotations.items())
            for annotation in frame_annotations
        ]
        data = {
            "session_id": self._session.session_id if self._session else "unknown",
            "total_annotations": len(annotations),
            "annotations": annotations,
            "pitch_scores": {pitch_id: score.value for pitch_id, score in self._pitch_scores.items()},
        }
        with output_path.open("w") as handle:
            json.dump(data, handle, indent=2)
        logger.info(f"Exported {len(annotations)} annotations to {output_path}")

    def get_pitch_score_summary(self) -> dict[str, int]:
        """Return counts for each score value."""
        summary = {score.value: 0 for score in PitchScore}
        for score in self._pitch_scores.values():
            summary[score.value] += 1
        return summary

    @property
    def session(self) -> Optional[LoadedSession]:
        return self._session

    @property
    def video_reader(self) -> VideoReader:
        return self._video_reader

    @property
    def detector_config(self) -> Optional[DetectorConfig]:
        return self._detector_config

    @property
    def current_frame_index(self) -> int:
        return self._video_reader.current_frame_index

    @property
    def total_frames(self) -> int:
        return self._video_reader.total_frames

    @property
    def playback_speed(self) -> float:
        return self._playback_speed

    @playback_speed.setter
    def playback_speed(self, speed: float) -> None:
        self._playback_speed = max(0.1, min(2.0, speed))

    def close(self) -> None:
        """Release playback resources and review state."""
        self._video_reader.close()
        self._session = None
        self._annotations.clear()
        self._pitch_scores.clear()
        logger.info("Review service closed")


__all__ = ["Annotation", "PitchScore", "ReviewService"]
