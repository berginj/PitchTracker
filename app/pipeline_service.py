"""In-process pipeline service to back the UI."""

from __future__ import annotations

import csv
import json
import queue
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np

from capture import CameraDevice, SimulatedCamera, UvcCamera
from capture.camera_device import CameraStats
from capture.opencv_backend import OpenCVCamera
from configs.lane_io import load_lane_rois
from configs.roi_io import load_rois
from configs.settings import AppConfig
from contracts import Detection, Frame, PitchMetrics, StereoObservation
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig
from detect.config import FilterConfig, Mode
from detect.lane import LaneGate, LaneRoi
from detect.ml_detector import MlDetector
from exceptions import (
    CameraConfigurationError,
    CameraConnectionError,
    CameraNotFoundError,
    DetectionError,
    FileWriteError,
    InvalidROIError,
    ModelInferenceError,
    ModelLoadError,
    PitchTrackerError,
    RecordingError,
)
from integrations.radar import NullRadarGun, RadarGunClient
from log_config.logger import get_logger
from metrics.simple_metrics import (
    PlateMetricsStub,
    compute_plate_from_observations,
    compute_plate_stub,
)
from metrics.strike_zone import StrikeResult, build_strike_zone, is_strike
from record.recorder import RecordingBundle
from stereo import StereoLaneGate
from stereo.association import StereoMatch
from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry
from track.simple_tracker import SimpleTracker
from trajectory.contracts import TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter

from app.pipeline.utils import (
    build_session_summary,
    build_stereo_matches,
    gate_detections,
    stats_to_dict,
)
from app.pipeline.config_service import ConfigService
from app.pipeline.initialization import PipelineInitializer
from app.pipeline.camera_management import CameraManager
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.recording.session_recorder import SessionRecorder
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.pipeline.analysis.session_summary import SessionManager
from app.pipeline.pitch_tracking_v2 import PitchStateMachineV2, PitchConfig, PitchData

logger = get_logger(__name__)


@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    created_utc: str
    schema_version: str


@dataclass(frozen=True)
class PitchSummary:
    pitch_id: str
    t_start_ns: int
    t_end_ns: int
    is_strike: bool
    zone_row: Optional[int]
    zone_col: Optional[int]
    run_in: float
    rise_in: float
    speed_mph: Optional[float]
    rotation_rpm: Optional[float]
    sample_count: int
    trajectory_plate_x_ft: Optional[float] = None
    trajectory_plate_y_ft: Optional[float] = None
    trajectory_plate_z_ft: Optional[float] = None
    trajectory_plate_t_ns: Optional[int] = None
    trajectory_model: Optional[str] = None
    trajectory_expected_error_ft: Optional[float] = None
    trajectory_confidence: Optional[float] = None


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    pitch_count: int
    strikes: int
    balls: int
    heatmap: List[List[int]]
    pitches: List[PitchSummary]


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
    ) -> None:
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
        """Run calibration and return a profile summary."""

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
        """Set detection threading mode ("per_camera" or "worker_pool")."""

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


class InProcessPipelineService(PipelineService):
    def __init__(self, backend: str = "uvc", radar_client: Optional[RadarGunClient] = None) -> None:
        self._backend = backend
        self._initializer = PipelineInitializer()
        self._camera_mgr = CameraManager(backend, self._initializer)
        self._detect_queue_size = 6
        self._detection_pool: Optional[DetectionThreadPool] = None
        self._detection_processor: Optional[DetectionProcessor] = None
        self._lane_gate: Optional[LaneGate] = None
        self._plate_gate: Optional[LaneGate] = None
        self._stereo_gate: Optional[StereoLaneGate] = None
        self._plate_stereo_gate: Optional[StereoLaneGate] = None
        self._detectors_by_camera: Dict[str, object] = {}
        self._lane_polygon: Optional[list[tuple[float, float]]] = None
        self._stereo: Optional[SimpleStereoMatcher] = None
        self._recording = False
        self._recorded_frames: list[Frame] = []
        self._pitch_id = "pitch-unknown"
        self._config: Optional[AppConfig] = None
        self._config_service: Optional[ConfigService] = None
        self._config_path: Optional[Path] = None
        self._record_dir: Optional[Path] = None
        self._record_session: Optional[str] = None
        self._record_mode: Optional[str] = None
        self._session_recorder: Optional[SessionRecorder] = None
        self._pitch_recorder: Optional[PitchRecorder] = None
        self._pitch_analyzer: Optional[PitchAnalyzer] = None
        self._session_manager: Optional[SessionManager] = None
        self._pitch_tracker: Optional[PitchStateMachineV2] = None
        self._radar_client: RadarGunClient = radar_client or NullRadarGun()
        self._manual_speed_mph: Optional[float] = None
        self._record_lock = threading.Lock()
        self._session_active = False
        self._pitch_id = "pitch-unknown"
        self._last_session_summary = SessionSummary(
            session_id="session",
            pitch_count=0,
            strikes=0,
            balls=0,
            heatmap=[[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            pitches=[],
        )

        # Wire camera frame callback
        self._camera_mgr.set_frame_callback(self._on_frame_captured)

    def _on_frame_captured(self, label: str, frame: Frame) -> None:
        """Callback when camera captures a frame.

        Handles frame routing:
        1. Buffer for pitch pre-roll (ALWAYS, before pitch detection)
        2. Write to session recording if active
        3. Write to pitch recording if active
        4. Enqueue for detection

        Args:
            label: Camera label ("left" or "right")
            frame: Captured frame
        """
        # Buffer for pitch pre-roll (V2: ALWAYS buffer, not just when pitch_recorder exists)
        if self._pitch_tracker and self._session_active:
            self._pitch_tracker.buffer_frame(label, frame)

        # Write to session recording if active
        if self._recording:
            self._write_record_frame_single(label, frame)

        # Enqueue for detection
        if self._detection_pool:
            self._detection_pool.enqueue_frame(label, frame)

    def _detect_frame(self, label: str, frame: Frame) -> list[Detection]:
        """Callback for frame detection.

        Args:
            label: Camera label
            frame: Frame to detect

        Returns:
            List of detections
        """
        detector = self._detectors_by_camera.get(label)
        if detector is None:
            return []
        try:
            return detector.detect(frame)
        except Exception:
            return []

    def _on_detection_result(self, label: str, frame: Frame, detections: list[Detection]) -> None:
        """Callback when detection result is ready.

        Args:
            label: Camera label
            frame: Detected frame
            detections: Detection results
        """
        if self._detection_processor:
            self._detection_processor.process_detection_result(label, frame, detections)

    def _on_stereo_pair(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: list[Detection],
        right_detections: list[Detection],
        observations: List[StereoObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        """Callback when stereo pair is processed.

        Args:
            left_frame: Left camera frame
            right_frame: Right camera frame
            left_detections: Left camera detections
            right_detections: Right camera detections
            observations: Triangulated observations
            lane_count: Number of lane detections
            plate_count: Number of plate detections
        """
        # Track observations and update pitch state
        if self._pitch_tracker:
            for obs in observations:
                self._pitch_tracker.add_observation(obs)

            frame_ns = max(left_frame.t_capture_monotonic_ns, right_frame.t_capture_monotonic_ns)
            obs_count = len(observations)
            self._pitch_tracker.update(frame_ns, lane_count, plate_count, obs_count)

    def _on_pitch_start(self, pitch_index: int, pitch_data: PitchData) -> None:
        """Callback when pitch starts (V2).

        Args:
            pitch_index: Pitch index (1-based)
            pitch_data: Complete pitch data with pre-roll frames and ramp-up observations
        """
        session = self._record_session or "session"
        self._pitch_id = f"{session}-pitch-{pitch_index:03d}"

        # Create and start pitch recorder
        if self._config and self._session_recorder:
            session_dir = self._session_recorder.get_session_dir()
            if session_dir:
                self._pitch_recorder = PitchRecorder(self._config, session_dir, self._pitch_id)
                self._pitch_recorder.start_pitch()

                # Write pre-roll frames (V2: These are captured BEFORE pitch detection)
                for cam_label, frame in pitch_data.pre_roll_frames:
                    self._pitch_recorder.write_frame(cam_label, frame)

    def _on_pitch_end(self, pitch_data: PitchData) -> None:
        """Callback when pitch ends (V2).

        Args:
            pitch_data: Complete pitch data with accurate timing and all observations
        """
        if self._pitch_analyzer is None or self._session_manager is None:
            return

        # Extract data from PitchData (V2: accurate start/end times)
        observations = pitch_data.observations
        start_ns = pitch_data.start_ns  # V2: Correct start time (first detection)
        end_ns = pitch_data.end_ns      # V2: Correct end time (last detection)

        # Analyze pitch
        summary = self._pitch_analyzer.analyze_pitch(
            pitch_id=self._pitch_id,
            start_ns=start_ns,
            end_ns=end_ns,
            observations=observations,
        )

        # Add to session
        self._session_manager.add_pitch(summary, observations)
        self._last_session_summary = self._session_manager.get_summary()

        # End pitch recording (continue for post-roll)
        if self._pitch_recorder:
            self._pitch_recorder.end_pitch(end_ns)
            # Write manifest
            config_path = str(self._config_path) if self._config_path else None
            self._pitch_recorder.write_manifest(summary, config_path)

    def start_capture(
        self,
        config: AppConfig,
        left_serial: str,
        right_serial: str,
        config_path: Optional[Path] = None,
    ) -> None:
        """Start capture on both cameras with error handling.

        Args:
            config: Application configuration
            left_serial: Left camera serial number
            right_serial: Right camera serial number
            config_path: Path to active config file

        Raises:
            CameraNotFoundError: If camera serials are not found
            CameraConnectionError: If cameras fail to open
            CameraConfigurationError: If camera configuration fails
            InvalidROIError: If ROI loading fails
            ModelLoadError: If ML detector model fails to load
        """
        logger.info(f"Starting capture with left={left_serial}, right={right_serial}")

        try:
            self._config = config
            self._config_service = ConfigService(config)
            self._config_path = config_path
            self._record_dir = Path(config.recording.output_dir)
            self._detect_queue_size = config.camera.queue_depth or 6

            # Start camera capture (opens, configures, starts threads)
            try:
                self._camera_mgr.start_capture(config, left_serial, right_serial)
            except (CameraConnectionError, CameraConfigurationError) as exc:
                # Camera errors - let them propagate
                raise

            # Get camera IDs from camera manager
            left_id, right_id = self._camera_mgr.get_camera_ids()

            # Load ROIs
            try:
                logger.debug("Loading ROIs")
                (
                    self._lane_polygon,
                    self._lane_gate,
                    self._stereo_gate,
                    self._plate_gate,
                    self._plate_stereo_gate,
                ) = PipelineInitializer.load_rois(left_id, right_id)
            except Exception as exc:
                logger.error(f"Failed to load ROIs: {exc}")
                self._camera_mgr.stop_capture()
                raise InvalidROIError(f"Failed to load ROI configuration: {exc}") from exc

            # Initialize detector
            try:
                logger.debug("Initializing detector")
                self._initializer.initialize_detector_config(config)
                self._detectors_by_camera = self._initializer.build_detectors(
                    left_id, right_id, self._lane_polygon
                )
                if self._initializer._detector_type == "ml":
                    self._initializer.warmup_detectors(self._detectors_by_camera, config)
            except Exception as exc:
                logger.error(f"Failed to initialize detector: {exc}")
                self._camera_mgr.stop_capture()
                if "model" in str(exc).lower() or "onnx" in str(exc).lower():
                    raise ModelLoadError(f"Failed to load detector model: {exc}") from exc
                raise DetectionError(f"Failed to initialize detector: {exc}") from exc

            # Initialize stereo
            try:
                logger.debug("Initializing stereo")
                self._stereo = PipelineInitializer.create_stereo_matcher(config)
            except Exception as exc:
                logger.error(f"Failed to initialize stereo: {exc}")
                self._camera_mgr.stop_capture()
                raise PitchTrackerError(f"Failed to initialize stereo system: {exc}") from exc

            # Create detection processor
            try:
                logger.debug("Creating detection processor")
                self._detection_processor = DetectionProcessor(
                    config=config,
                    stereo_matcher=self._stereo,
                    lane_gate=self._lane_gate,
                    plate_gate=self._plate_gate,
                    stereo_gate=self._stereo_gate,
                    plate_stereo_gate=self._plate_stereo_gate,
                    get_ball_radius_fn=lambda: self._config_service.get_ball_radius_in() if self._config_service else 1.45,
                )
                self._detection_processor.set_stereo_pair_callback(self._on_stereo_pair)
            except Exception as exc:
                logger.error(f"Failed to create detection processor: {exc}")
                self._camera_mgr.stop_capture()
                raise DetectionError(f"Failed to create detection processor: {exc}") from exc

            # Create and start detection thread pool
            try:
                logger.debug("Starting detection threads")
                self._detection_pool = DetectionThreadPool(mode="per_camera", worker_count=2)
                self._detection_pool.set_detect_callback(self._detect_frame)
                self._detection_pool.set_stereo_callback(self._on_detection_result)
                self._detection_pool.start(queue_size=self._detect_queue_size)
            except Exception as exc:
                logger.error(f"Failed to start detection threads: {exc}")
                self._camera_mgr.stop_capture()
                raise CameraConnectionError(f"Failed to start detection threads: {exc}") from exc

            logger.info("Capture started successfully")

        except (CameraNotFoundError, CameraConnectionError, CameraConfigurationError,
                InvalidROIError, ModelLoadError, DetectionError) as exc:
            # Re-raise our custom exceptions
            raise
        except Exception as exc:
            # Catch any unexpected errors
            logger.exception("Unexpected error during capture start")
            self._camera_mgr.stop_capture()
            raise PitchTrackerError(f"Unexpected error starting capture: {exc}") from exc

    def stop_capture(self) -> None:
        """Stop capture on both cameras with error handling.

        Ensures all resources are properly cleaned up even if errors occur.
        """
        logger.info("Stopping capture")

        try:
            # Stop detection threads
            try:
                if self._detection_pool:
                    self._detection_pool.stop()
                logger.debug("Detection threads stopped")
            except Exception as exc:
                logger.warning(f"Error stopping detection threads: {exc}")

            # Stop camera capture (stops threads, closes cameras)
            self._camera_mgr.stop_capture()

            logger.info("Capture stopped successfully")

        except Exception as exc:
            logger.exception("Unexpected error during capture stop")
            # Don't raise - we want stop to be best-effort cleanup

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Get latest preview frames from both cameras.

        Returns:
            Tuple of (left_frame, right_frame)

        Raises:
            CameraConnectionError: If capture is not started or cameras not available
            PitchTrackerError: If frames are not yet available
        """
        return self._camera_mgr.get_preview_frames()

    def start_recording(
        self,
        pitch_id: Optional[str] = None,
        session_name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> None:
        self._recording = True
        self._recorded_frames = []
        if pitch_id:
            self._pitch_id = pitch_id
        else:
            self._pitch_id = time.strftime("pitch-%Y%m%d-%H%M%S", time.gmtime())
        self._record_session = session_name
        self._record_mode = mode
        self._session_active = True
        if self._pitch_tracker:
            self._pitch_tracker.reset()
        self._last_session_summary = SessionSummary(
            session_id=self._record_session or "session",
            pitch_count=0,
            strikes=0,
            balls=0,
            heatmap=[[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            pitches=[],
        )
        self._start_recording_io()

    def set_record_directory(self, path: Optional[Path]) -> None:
        self._record_dir = path

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        self._manual_speed_mph = speed_mph

    def stop_recording(self) -> RecordingBundle:
        self._recording = False
        if self._pitch_tracker:
            self._pitch_tracker.force_end()
        self._session_active = False
        self._stop_recording_io()
        metrics = PitchMetrics(
            pitch_id=self._pitch_id,
            t_start_ns=0,
            t_end_ns=0,
            velo_mph=0.0,
            HB_in=0.0,
            iVB_in=0.0,
            release_xyz_ft=(0.0, 0.0, 0.0),
            approach_angles_deg=(0.0, 0.0),
            confidence=0.0,
        )
        return RecordingBundle(
            pitch_id=self._pitch_id,
            frames=[],
            detections=[],
            track=[],
            metrics=metrics,
        )

    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        created_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return CalibrationProfile(profile_id=profile_id, created_utc=created_utc, schema_version="1.0.0")

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        return self._camera_mgr.get_stats()

    def get_plate_metrics(self) -> PlateMetricsStub:
        if self._detection_processor:
            return self._detection_processor.get_plate_metrics()
        return PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)

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
        self._initializer.update_detector_config(
            config,
            mode,
            detector_type,
            model_path,
            model_input_size,
            model_conf_threshold,
            model_class_id,
            model_format,
        )
        left_id, right_id = self._camera_mgr.get_camera_ids()
        if left_id and right_id:
            self._detectors_by_camera = self._initializer.build_detectors(
                left_id, right_id, self._lane_polygon
            )

    def set_detection_threading(self, mode: str, worker_count: int) -> None:
        if mode not in ("per_camera", "worker_pool"):
            raise ValueError(f"Unknown detection threading mode: {mode}")

        if self._detection_pool:
            # Update mode and restart if running
            is_running = self._detection_pool.is_running()
            if is_running:
                self._detection_pool.stop()
            self._detection_pool.set_mode(mode, worker_count)
            if is_running:
                self._detection_pool.start(queue_size=self._detect_queue_size)

    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        if self._detection_processor:
            return self._detection_processor.get_latest_detections()
        return {}

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        if self._detection_processor:
            return self._detection_processor.get_latest_gated_detections()
        return {}

    def get_strike_result(self) -> StrikeResult:
        if self._detection_processor:
            return self._detection_processor.get_strike_result()
        return StrikeResult(is_strike=False, sample_count=0)

    def set_ball_type(self, ball_type: str) -> None:
        if self._config_service is not None:
            self._config_service.set_ball_type(ball_type)

    def set_batter_height_in(self, height_in: float) -> None:
        if self._config_service is not None:
            self._config_service.update_batter_height(height_in)
            # Sync back to self._config for backward compatibility
            self._config = self._config_service.get_config()
            # Update pitch analyzer
            if self._pitch_analyzer:
                self._pitch_analyzer.update_config(self._config)

    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        if self._config_service is not None:
            self._config_service.update_strike_zone_ratios(top_ratio, bottom_ratio)
            # Sync back to self._config for backward compatibility
            self._config = self._config_service.get_config()
            # Update pitch analyzer
            if self._pitch_analyzer:
                self._pitch_analyzer.update_config(self._config)

    def get_session_summary(self) -> SessionSummary:
        return self._last_session_summary

    def get_recent_pitch_paths(self) -> list[list[StereoObservation]]:
        if self._session_manager:
            return [list(path) for path in self._session_manager.get_recent_paths()]
        return []

    def get_session_dir(self) -> Optional[Path]:
        if self._session_recorder:
            return self._session_recorder.get_session_dir()
        return None

    def _start_recording_io(self) -> None:
        if self._config is None:
            return

        # Initialize session recorder
        self._session_recorder = SessionRecorder(self._config, self._record_dir)
        session_dir = self._session_recorder.start_session(
            self._record_session or "session", self._pitch_id
        )

        # Initialize pitch analyzer
        self._pitch_analyzer = PitchAnalyzer(
            config=self._config,
            get_ball_radius_fn=lambda: self._config_service.get_ball_radius_in() if self._config_service else 1.45,
            radar_speed_fn=lambda: self._radar_client.latest_speed_mph() if self._manual_speed_mph is None else self._manual_speed_mph,
        )

        # Initialize session manager
        self._session_manager = SessionManager(self._record_session or "session")

        # Initialize pitch state machine (V2: robust architecture with thread safety)
        pitch_config = PitchConfig(
            min_active_frames=self._config.recording.session_min_active_frames,
            end_gap_frames=self._config.recording.session_end_gap_frames,
            use_plate_gate=self._plate_gate is not None,
            min_observations=3,  # V2: Minimum observations to save pitch
            min_duration_ms=100.0,  # V2: Minimum duration to confirm pitch
            pre_roll_ms=float(self._config.recording.pre_roll_ms),  # V2: Pre-roll window
            frame_rate=float(self._config.camera.fps),  # V2: For timing calculations
        )
        self._pitch_tracker = PitchStateMachineV2(pitch_config)
        self._pitch_tracker.set_callbacks(
            on_pitch_start=self._on_pitch_start,
            on_pitch_end=self._on_pitch_end,
        )

    def _stop_recording_io(self) -> None:
        # Close pitch recording if active
        if self._pitch_recorder:
            self._pitch_recorder.close(force=True)
            self._pitch_recorder = None

        # Stop session recording
        if self._session_recorder:
            config_path = str(self._config_path) if self._config_path else None
            self._session_recorder.stop_session(
                config_path,
                self._pitch_id,
                self._record_session,
                self._record_mode,
                self._manual_speed_mph,
            )
            self._write_session_summary()

    def _write_record_frame_single(self, label: str, frame: Frame) -> None:
        if not self._recording:
            return
        # Write to session recording
        if self._session_recorder:
            self._session_recorder.write_frame(label, frame)
        # Write to pitch recording if active (V2: pre-roll handled by state machine)
        if self._pitch_recorder:
            if self._pitch_recorder.is_active():
                self._pitch_recorder.write_frame(label, frame)
                # Check if post-roll is complete
                if self._pitch_recorder.should_close():
                    self._pitch_recorder.close()
                    self._pitch_recorder = None


    def _write_session_summary(self) -> None:
        if self._session_recorder:
            self._session_recorder.write_session_summary(self._last_session_summary)

