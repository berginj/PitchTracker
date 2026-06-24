"""Service boundary for the legacy-compatible pipeline API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.contracts import CalibrationProfile, SessionSummary
from configs.settings import AppConfig
from contracts import Detection, Frame, StereoObservation
from detect.config import DetectorConfig as CvDetectorConfig
from detect.config import Mode
from metrics.simple_metrics import PlateMetricsStub
from metrics.strike_zone import StrikeResult
from record.recorder import RecordingBundle


class PipelineService(ABC):
    @abstractmethod
    def start_capture(
        self,
        config: AppConfig,
        left_serial: str,
        right_serial: str,
        config_path: Optional[Path] = None,
    ) -> None:
        """Start capture on both cameras."""

    @abstractmethod
    def stop_capture(self) -> None:
        """Stop capture on both cameras."""

    @abstractmethod
    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Return the latest frames for UI preview."""

    @abstractmethod
    def start_recording(
        self,
        pitch_id: Optional[str] = None,
        session_name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """Begin recording frames and metadata."""

    @abstractmethod
    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for recordings."""

    @abstractmethod
    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        """Set manual speed from external device."""

    @abstractmethod
    def stop_recording(self) -> RecordingBundle:
        """Stop recording and return the bundle."""

    @abstractmethod
    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        """Run calibration and return a profile summary.

        Runtime implementations may reject this call when calibration is owned
        by setup/tooling services rather than the active capture pipeline.
        """

    @abstractmethod
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Return capture stats for both cameras."""

    @abstractmethod
    def get_plate_metrics(self) -> PlateMetricsStub:
        """Return latest plate-gated metrics (stubbed if unavailable)."""

    @abstractmethod
    def set_detector_config(
        self,
        config: CvDetectorConfig,
        mode: Mode,
        detector_type: str = "classical",
        model_path: Optional[str] = None,
        model_input_size: Tuple[int, int] = (640, 640),
        model_conf_threshold: float = 0.25,
        model_class_id: int = 0,
        model_format: str = "yolo_v5",
    ) -> None:
        """Update detector configuration for the active session."""

    @abstractmethod
    def set_detection_threading(self, mode: str, worker_count: int) -> None:
        """Set detection threading mode."""

    @abstractmethod
    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        """Return latest raw detections by camera id."""

    @abstractmethod
    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        """Return latest gated detections by camera id and gate name."""

    @abstractmethod
    def get_strike_result(self) -> StrikeResult:
        """Return latest strike determination."""

    @abstractmethod
    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type for strike detection."""

    @abstractmethod
    def set_batter_height_in(self, height_in: float) -> None:
        """Set batter height for strike zone calculation."""

    @abstractmethod
    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        """Set strike zone top/bottom ratios for the active session."""

    @abstractmethod
    def get_session_summary(self) -> SessionSummary:
        """Return the latest session summary."""

    @abstractmethod
    def get_recent_pitch_paths(self) -> list[list[StereoObservation]]:
        """Return recent pitch observation paths."""

    @abstractmethod
    def get_session_dir(self) -> Optional[Path]:
        """Return the current session directory if available."""
