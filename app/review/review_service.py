"""Review service for managing session playback and analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

from app.review.session_loader import LoadedPitch, LoadedSession, SessionLoader
from app.review.video_reader import PlaybackState, VideoReader
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig, Mode
from log_config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Annotation:
    """Manual annotation for a frame.

    Attributes:
        frame_index: Frame index (0-based)
        camera: "left" or "right"
        x: X coordinate of annotation
        y: Y coordinate of annotation
        annotation_type: Type of annotation ("manual", "corrected", etc.)
        confidence: Confidence score (0.0-1.0)
        note: Optional note or description
    """
    frame_index: int
    camera: str
    x: float
    y: float
    annotation_type: str = "manual"
    confidence: float = 1.0
    note: Optional[str] = None


class PitchScore(Enum):
    """Quality score for pitch detection."""
    GOOD = "good"        # Detection worked perfectly
    PARTIAL = "partial"  # Some frames detected, some missed
    MISSED = "missed"    # Detection completely failed
    UNSCORED = "unscored"  # Not yet scored


class ReviewService:
    """Service for managing review mode functionality.

    Orchestrates session loading, video playback, detection re-processing,
    annotation management, and configuration export.

    Example:
        >>> service = ReviewService()
        >>> session = service.load_session(Path("recordings/session-2026-01-19_001"))
        >>> service.seek_to_frame(100)
        >>> left, right = service.get_current_frames()
        >>> service.update_detector_config(frame_diff_threshold=22.0)
        >>> detections = service.run_detection_on_current_frame()
    """

    def __init__(self):
        """Initialize review service."""
        self._session: Optional[LoadedSession] = None
        self._video_reader = VideoReader()

        # Detection configuration (starts with default)
        self._detector_config: Optional[DetectorConfig] = None
        self._detector_mode = Mode.MODE_A

        # Detectors for left and right cameras
        self._detector_left: Optional[ClassicalDetector] = None
        self._detector_right: Optional[ClassicalDetector] = None

        # Annotations and pitch scores
        self._annotations: dict[int, list[Annotation]] = {}  # frame_index -> list of annotations
        self._pitch_scores: dict[str, PitchScore] = {}  # pitch_id -> score

        # Playback state
        self._playback_speed = 1.0

        logger.debug("ReviewService initialized")

    def load_session(self, session_dir: Path) -> LoadedSession:
        """Load a session for review.

        Args:
            session_dir: Path to session directory

        Returns:
            LoadedSession object

        Raises:
            FileNotFoundError: If session or videos not found
            ValueError: If session is invalid
        """
        logger.info(f"Loading session for review: {session_dir}")

        # Load session data
        self._session = SessionLoader.load_session(session_dir)

        # Open videos
        if not self._session.left_video_path.exists():
            raise FileNotFoundError(f"Left video not found: {self._session.left_video_path}")
        if not self._session.right_video_path.exists():
            raise FileNotFoundError(f"Right video not found: {self._session.right_video_path}")

        self._video_reader.open_videos(
            self._session.left_video_path,
            self._session.right_video_path
        )

        # Initialize detector config from original config if available
        if self._session.original_config:
            self._detector_config = self._session.original_config.detector
            self._detector_mode = Mode(self._session.original_config.detector.mode)
            logger.info("Loaded original detector configuration")
        else:
            # Use default config
            self._detector_config = DetectorConfig(
                type="classical",
                model_path=None,
                model_input_size=(640, 640),
                model_conf_threshold=0.25,
                model_class_id=0,
                model_format="yolo_v5",
                mode="MODE_A",
                frame_diff_threshold=18.0,
                bg_diff_threshold=12.0,
                bg_alpha=0.01,
                edge_threshold=50.0,
                blob_threshold=20.0,
                runtime_budget_ms=10.0,
                crop_padding_px=10,
                min_consecutive=3,
                filters=FilterConfig(
                    min_area=12,
                    max_area=500,
                    min_circularity=0.1,
                    max_circularity=1.0,
                    min_velocity=10.0,
                    max_velocity=200.0,
                ),
            )
            logger.info("Using default detector configuration")

        # Initialize pitch scores to unscored
        for pitch in self._session.pitches:
            self._pitch_scores[pitch.pitch_id] = PitchScore.UNSCORED

        # Clear annotations
        self._annotations.clear()

        logger.info(
            f"Session loaded: {self._session.session_id}, "
            f"{len(self._session.pitches)} pitches, "
            f"{self._video_reader.total_frames} frames"
        )

        return self._session

    def get_current_frames(self) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get current left and right frames.

        Returns:
            Tuple of (left_frame, right_frame) as numpy arrays
        """
        return self._video_reader.read_frames()

    def seek_to_frame(self, frame_index: int) -> bool:
        """Seek to specific frame.

        Args:
            frame_index: Frame index to seek to (0-based)

        Returns:
            True if seek successful
        """
        return self._video_reader.seek_to_frame(frame_index)

    def seek_to_pitch(self, pitch_index: int) -> bool:
        """Seek to start of specific pitch.

        Args:
            pitch_index: Pitch index (0-based)

        Returns:
            True if seek successful, False if pitch index invalid
        """
        if not self._session or pitch_index < 0 or pitch_index >= len(self._session.pitches):
            logger.warning(f"Invalid pitch index: {pitch_index}")
            return False

        pitch = self._session.pitches[pitch_index]

        # Calculate frame index from pitch start time
        # This is approximate - need to correlate with video timestamps
        # For now, just estimate based on frame rate
        # TODO: Load and parse timestamp CSV files for accurate frame mapping

        logger.info(f"Seeking to pitch {pitch.pitch_id}")
        # Placeholder: just seek to a frame proportional to pitch number
        # In reality, we need to parse timestamps
        frame_index = pitch_index * 100  # Rough estimate
        return self.seek_to_frame(frame_index)

    def step_forward(self, num_frames: int = 1) -> bool:
        """Step forward by frames.

        Args:
            num_frames: Number of frames to advance

        Returns:
            True if step successful
        """
        return self._video_reader.step_forward(num_frames)

    def step_backward(self, num_frames: int = 1) -> bool:
        """Step backward by frames.

        Args:
            num_frames: Number of frames to go back

        Returns:
            True if step successful
        """
        return self._video_reader.step_backward(num_frames)

    def seek_to_start(self) -> bool:
        """Seek to start of video."""
        return self._video_reader.seek_to_start()

    def seek_to_end(self) -> bool:
        """Seek to end of video."""
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
        """Update detector configuration parameters.

        Args:
            frame_diff_threshold: Frame differencing threshold
            bg_diff_threshold: Background subtraction threshold
            min_area: Minimum blob area
            max_area: Maximum blob area
            min_circularity: Minimum circularity
            mode: Detection mode (MODE_A, MODE_B, MODE_C)
        """
        if not self._detector_config:
            logger.warning("No detector config loaded")
            return

        # Update parameters (create new config since it's frozen)
        filters = self._detector_config.filters
        new_filters = FilterConfig(
            min_area=min_area if min_area is not None else filters.min_area,
            max_area=max_area if max_area is not None else filters.max_area,
            min_circularity=min_circularity if min_circularity is not None else filters.min_circularity,
            max_circularity=filters.max_circularity,
            min_velocity=filters.min_velocity,
            max_velocity=filters.max_velocity,
        )

        self._detector_config = DetectorConfig(
            type=self._detector_config.type,
            model_path=self._detector_config.model_path,
            model_input_size=self._detector_config.model_input_size,
            model_conf_threshold=self._detector_config.model_conf_threshold,
            model_class_id=self._detector_config.model_class_id,
            model_format=self._detector_config.model_format,
            mode=mode.value if mode is not None else self._detector_config.mode,
            frame_diff_threshold=frame_diff_threshold if frame_diff_threshold is not None else self._detector_config.frame_diff_threshold,
            bg_diff_threshold=bg_diff_threshold if bg_diff_threshold is not None else self._detector_config.bg_diff_threshold,
            bg_alpha=self._detector_config.bg_alpha,
            edge_threshold=self._detector_config.edge_threshold,
            blob_threshold=self._detector_config.blob_threshold,
            runtime_budget_ms=self._detector_config.runtime_budget_ms,
            crop_padding_px=self._detector_config.crop_padding_px,
            min_consecutive=self._detector_config.min_consecutive,
            filters=new_filters,
        )

        if mode is not None:
            self._detector_mode = mode

        # Rebuild detectors with new config
        self._rebuild_detectors()

        logger.debug(f"Updated detector config: {self._detector_config}")

    def _rebuild_detectors(self) -> None:
        """Rebuild detectors with current configuration."""
        if not self._detector_config:
            return

        # Create detectors for both cameras
        self._detector_left = ClassicalDetector(
            config=self._detector_config,
            mode=self._detector_mode,
            roi_by_camera={},  # No ROI filtering in review mode
        )

        self._detector_right = ClassicalDetector(
            config=self._detector_config,
            mode=self._detector_mode,
            roi_by_camera={},
        )

        logger.debug("Rebuilt detectors with updated config")

    def run_detection_on_current_frame(self) -> tuple[list, list]:
        """Run detection on current frame for both cameras.

        Returns:
            Tuple of (left_detections, right_detections)
            Each is a list of Detection objects
        """
        if not self._detector_left or not self._detector_right:
            self._rebuild_detectors()

        left_frame, right_frame = self.get_current_frames()

        left_detections = []
        right_detections = []

        # Run detection on left frame
        if left_frame is not None and self._detector_left:
            try:
                # Convert to grayscale if needed
                import cv2
                if len(left_frame.shape) == 3:
                    gray_left = cv2.cvtColor(left_frame, cv2.COLOR_BGR2GRAY)
                else:
                    gray_left = left_frame

                # Create Frame contract
                frame_obj = Frame(
                    camera_id="left",
                    frame_index=self._video_reader.current_frame_index,
                    t_capture_monotonic_ns=0,
                    image=gray_left,
                    width=gray_left.shape[1],
                    height=gray_left.shape[0],
                    pixfmt="GRAY8",
                )

                left_detections = self._detector_left.detect(frame_obj)
            except Exception as e:
                logger.warning(f"Left detection failed: {e}")

        # Run detection on right frame
        if right_frame is not None and self._detector_right:
            try:
                # Convert to grayscale if needed
                import cv2
                if len(right_frame.shape) == 3:
                    gray_right = cv2.cvtColor(right_frame, cv2.COLOR_BGR2GRAY)
                else:
                    gray_right = right_frame

                # Create Frame contract
                frame_obj = Frame(
                    camera_id="right",
                    frame_index=self._video_reader.current_frame_index,
                    t_capture_monotonic_ns=0,
                    image=gray_right,
                    width=gray_right.shape[1],
                    height=gray_right.shape[0],
                    pixfmt="GRAY8",
                )

                right_detections = self._detector_right.detect(frame_obj)
            except Exception as e:
                logger.warning(f"Right detection failed: {e}")

        return left_detections, right_detections

    def add_annotation(self, frame_index: int, camera: str, x: float, y: float, note: str = "") -> None:
        """Add manual annotation at frame.

        Args:
            frame_index: Frame index
            camera: "left" or "right"
            x: X coordinate
            y: Y coordinate
            note: Optional note
        """
        annotation = Annotation(
            frame_index=frame_index,
            camera=camera,
            x=x,
            y=y,
            annotation_type="manual",
            confidence=1.0,
            note=note or None,
        )

        if frame_index not in self._annotations:
            self._annotations[frame_index] = []

        self._annotations[frame_index].append(annotation)
        logger.info(f"Added annotation at frame {frame_index}, {camera} ({x:.1f}, {y:.1f})")

    def score_pitch(self, pitch_id: str, score: PitchScore) -> None:
        """Score a pitch's detection quality.

        Args:
            pitch_id: Pitch identifier
            score: Quality score
        """
        self._pitch_scores[pitch_id] = score
        logger.info(f"Scored pitch {pitch_id}: {score.value}")

    def export_config(self, output_path: Path) -> None:
        """Export current detector configuration to YAML.

        Args:
            output_path: Path for output YAML file
        """
        if not self._detector_config:
            logger.warning("No detector config to export")
            return

        # TODO: Convert DetectorConfig to YAML format
        # For now, just save as JSON
        output_json = output_path.with_suffix('.json')

        config_dict = {
            "detector": {
                "type": self._detector_config.type,
                "mode": self._detector_config.mode,
                "frame_diff_threshold": self._detector_config.frame_diff_threshold,
                "bg_diff_threshold": self._detector_config.bg_diff_threshold,
                "bg_alpha": self._detector_config.bg_alpha,
                "edge_threshold": self._detector_config.edge_threshold,
                "blob_threshold": self._detector_config.blob_threshold,
                "runtime_budget_ms": self._detector_config.runtime_budget_ms,
                "crop_padding_px": self._detector_config.crop_padding_px,
                "min_consecutive": self._detector_config.min_consecutive,
                "filters": {
                    "min_area": self._detector_config.filters.min_area,
                    "max_area": self._detector_config.filters.max_area,
                    "min_circularity": self._detector_config.filters.min_circularity,
                    "max_circularity": self._detector_config.filters.max_circularity,
                    "min_velocity": self._detector_config.filters.min_velocity,
                    "max_velocity": self._detector_config.filters.max_velocity,
                },
            }
        }

        with open(output_json, 'w') as f:
            json.dump(config_dict, f, indent=2)

        logger.info(f"Exported detector config to {output_json}")

    def export_annotations(self, output_path: Path) -> None:
        """Export annotations to JSON.

        Args:
            output_path: Path for output JSON file
        """
        annotations_list = []
        for frame_index, frame_annotations in sorted(self._annotations.items()):
            for annotation in frame_annotations:
                annotations_list.append(asdict(annotation))

        data = {
            "session_id": self._session.session_id if self._session else "unknown",
            "total_annotations": len(annotations_list),
            "annotations": annotations_list,
            "pitch_scores": {pid: score.value for pid, score in self._pitch_scores.items()},
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(annotations_list)} annotations to {output_path}")

    def get_pitch_score_summary(self) -> dict[str, int]:
        """Get summary of pitch scores.

        Returns:
            Dictionary with counts for each score type
        """
        summary = {
            "good": 0,
            "partial": 0,
            "missed": 0,
            "unscored": 0,
        }

        for score in self._pitch_scores.values():
            summary[score.value] += 1

        return summary

    @property
    def session(self) -> Optional[LoadedSession]:
        """Get loaded session."""
        return self._session

    @property
    def video_reader(self) -> VideoReader:
        """Get video reader."""
        return self._video_reader

    @property
    def detector_config(self) -> Optional[DetectorConfig]:
        """Get current detector config."""
        return self._detector_config

    @property
    def current_frame_index(self) -> int:
        """Get current frame index."""
        return self._video_reader.current_frame_index

    @property
    def total_frames(self) -> int:
        """Get total frame count."""
        return self._video_reader.total_frames

    @property
    def playback_speed(self) -> float:
        """Get playback speed multiplier."""
        return self._playback_speed

    @playback_speed.setter
    def playback_speed(self, speed: float) -> None:
        """Set playback speed multiplier (0.1 to 2.0)."""
        self._playback_speed = max(0.1, min(2.0, speed))

    def close(self) -> None:
        """Close session and release resources."""
        self._video_reader.close()
        self._session = None
        self._annotations.clear()
        self._pitch_scores.clear()
        logger.info("Review service closed")
