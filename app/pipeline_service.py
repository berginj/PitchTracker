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
        self._trajectory_fitter = PhysicsDragFitter()
        self._current_pitch_observations: List[StereoObservation] = []
        self._recording = False
        self._recorded_frames: list[Frame] = []
        self._pitch_id = "pitch-unknown"
        self._config: Optional[AppConfig] = None
        self._config_service: Optional[ConfigService] = None
        self._config_path: Optional[Path] = None
        self._record_dir: Optional[Path] = None
        self._record_session: Optional[str] = None
        self._record_mode: Optional[str] = None
        self._record_left_writer = None
        self._record_right_writer = None
        self._record_left_csv = None
        self._record_right_csv = None
        self._session_left_writer = None
        self._session_right_writer = None
        self._session_left_csv = None
        self._session_right_csv = None
        self._session_dir: Optional[Path] = None
        self._radar_client: RadarGunClient = radar_client or NullRadarGun()
        self._pitch_left_writer = None
        self._pitch_right_writer = None
        self._pitch_left_csv = None
        self._pitch_right_csv = None
        self._pitch_post_end_ns: Optional[int] = None
        self._pitch_latest_ns: Dict[str, int] = {"left": 0, "right": 0}
        self._pre_roll_ns = 0
        self._post_roll_ns = 0
        self._pre_roll_left: deque[Frame] = deque()
        self._pre_roll_right: deque[Frame] = deque()
        self._manual_speed_mph: Optional[float] = None
        self._record_lock = threading.Lock()
        self._session_active = False
        self._pitch_active = False
        self._pitch_active_frames = 0
        self._pitch_gap_frames = 0
        self._pitch_index = 0
        self._pitch_start_ns = 0
        self._pitch_end_ns = 0
        self._session_pitches: List[PitchSummary] = []
        self._recent_pitch_paths: deque[list[StereoObservation]] = deque(maxlen=12)
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
        1. Write to session recording if active
        2. Buffer for pitch pre-roll
        3. Write to pitch recording if active
        4. Enqueue for detection

        Args:
            label: Camera label ("left" or "right")
            frame: Captured frame
        """
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
        # Track observations for current pitch
        for obs in observations:
            if self._pitch_active:
                self._current_pitch_observations.append(obs)

        # Update pitch state
        frame_ns = max(left_frame.t_capture_monotonic_ns, right_frame.t_capture_monotonic_ns)
        obs_count = len(observations)
        self._update_pitch_state(frame_ns, lane_count, plate_count, obs_count)

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
        self._session_pitches = []
        self._recent_pitch_paths.clear()
        self._pitch_index = 0
        self._pitch_active = False
        self._pitch_active_frames = 0
        self._pitch_gap_frames = 0
        self._current_pitch_observations = []
        self._last_session_summary = build_session_summary(
            self._record_session or "session",
            self._session_pitches,
        )
        self._start_recording_io()

    def set_record_directory(self, path: Optional[Path]) -> None:
        self._record_dir = path

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        self._manual_speed_mph = speed_mph

    def stop_recording(self) -> RecordingBundle:
        self._recording = False
        if self._pitch_active:
            self._finalize_pitch(self._pitch_end_ns or time.monotonic_ns())
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

    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        if self._config_service is not None:
            self._config_service.update_strike_zone_ratios(top_ratio, bottom_ratio)
            # Sync back to self._config for backward compatibility
            self._config = self._config_service.get_config()

    def get_session_summary(self) -> SessionSummary:
        return self._last_session_summary

    def get_recent_pitch_paths(self) -> list[list[StereoObservation]]:
        return [list(path) for path in self._recent_pitch_paths]

    def get_session_dir(self) -> Optional[Path]:
        return self._session_dir

    def _start_recording_io(self) -> None:
        if self._config is None:
            return
        base = self._record_session or self._pitch_id
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in base)
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        base_dir = self._record_dir or Path("recordings")
        self._session_dir = base_dir / f"{safe}_{timestamp}"
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._pre_roll_ns = int(self._config.recording.pre_roll_ms * 1e6)
        self._post_roll_ns = int(self._config.recording.post_roll_ms * 1e6)
        self._pre_roll_left.clear()
        self._pre_roll_right.clear()
        self._open_session_recording()

    def _stop_recording_io(self) -> None:
        self._close_pitch_recording(force=True)
        if self._session_dir is None:
            return
        self._close_session_recording()
        config_path = str(self._config_path) if self._config_path else "configs/default.yaml"
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "rig_id": None,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pitch_id": self._pitch_id,
            "session": self._record_session,
            "mode": self._record_mode,
            "measured_speed_mph": self._manual_speed_mph,
            "config_path": config_path,
            "calibration_profile_id": None,
            "session_summary": "session_summary.json",
            "session_summary_csv": "session_summary.csv",
            "session_left_video": "session_left.avi",
            "session_right_video": "session_right.avi",
            "session_left_timestamps": "session_left_timestamps.csv",
            "session_right_timestamps": "session_right_timestamps.csv",
        }
        (self._session_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )
        self._write_session_summary()

    def _write_record_frame_single(self, label: str, frame: Frame) -> None:
        if not self._recording:
            return
        self._buffer_pre_roll(label, frame)
        self._write_session_frame(label, frame)
        if self._pitch_active or self._pitch_post_end_ns is not None:
            self._write_pitch_frame(label, frame)

    def _open_session_recording(self) -> None:
        if self._config is None or self._session_dir is None:
            return
        left_path = self._session_dir / "session_left.avi"
        right_path = self._session_dir / "session_right.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._session_left_writer = cv2.VideoWriter(
            str(left_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        self._session_right_writer = cv2.VideoWriter(
            str(right_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        left_csv = (self._session_dir / "session_left_timestamps.csv").open("w", newline="")
        right_csv = (self._session_dir / "session_right_timestamps.csv").open("w", newline="")
        self._session_left_csv = (left_csv, csv.writer(left_csv))
        self._session_right_csv = (right_csv, csv.writer(right_csv))
        self._session_left_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        self._session_right_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )

    def _close_session_recording(self) -> None:
        with self._record_lock:
            if self._session_left_writer is not None:
                self._session_left_writer.release()
                self._session_left_writer = None
            if self._session_right_writer is not None:
                self._session_right_writer.release()
                self._session_right_writer = None
            if self._session_left_csv is not None:
                self._session_left_csv[0].close()
                self._session_left_csv = None
            if self._session_right_csv is not None:
                self._session_right_csv[0].close()
                self._session_right_csv = None

    def _write_session_frame(self, label: str, frame: Frame) -> None:
        if self._session_left_writer is None or self._session_right_writer is None:
            return
        image = frame.image
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        with self._record_lock:
            if label == "left" and self._session_left_writer is not None:
                self._session_left_writer.write(image)
                if self._session_left_csv is not None:
                    self._session_left_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
            elif label == "right" and self._session_right_writer is not None:
                self._session_right_writer.write(image)
                if self._session_right_csv is not None:
                    self._session_right_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )


    def _update_pitch_state(
        self,
        frame_ns: int,
        lane_count: int,
        plate_count: int,
        obs_count: int,
    ) -> None:
        if not self._session_active or self._config is None:
            return
        min_active = self._config.recording.session_min_active_frames
        end_gap = self._config.recording.session_end_gap_frames
        if self._plate_gate is None:
            active = lane_count > 0
        else:
            active = plate_count > 0 or obs_count > 0
        if active:
            self._pitch_gap_frames = 0
            self._pitch_active_frames += 1
            self._pitch_end_ns = frame_ns
            if not self._pitch_active and self._pitch_active_frames >= min_active:
                self._start_pitch(frame_ns)
        else:
            if self._pitch_active:
                self._pitch_gap_frames += 1
                if self._pitch_gap_frames >= end_gap:
                    self._finalize_pitch(frame_ns)
            else:
                self._pitch_active_frames = 0

    def _start_pitch(self, frame_ns: int) -> None:
        self._pitch_active = True
        self._pitch_start_ns = frame_ns
        self._pitch_index += 1
        self._current_pitch_observations = []
        self._plate_observations.clear()
        session = self._record_session or "session"
        self._pitch_id = f"{session}-pitch-{self._pitch_index:03d}"
        self._open_pitch_recording()

    def _finalize_pitch(self, frame_ns: int) -> None:
        self._pitch_active = False
        self._pitch_active_frames = 0
        self._pitch_gap_frames = 0
        self._pitch_end_ns = frame_ns
        self._pitch_post_end_ns = frame_ns + self._post_roll_ns
        if self._config is None:
            return
        zone = build_strike_zone(
            plate_z_ft=self._config.metrics.plate_plane_z_ft,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
            batter_height_in=self._config.strike_zone.batter_height_in,
            top_ratio=self._config.strike_zone.top_ratio,
            bottom_ratio=self._config.strike_zone.bottom_ratio,
        )
        radius_in = self._config_service.get_ball_radius_in() if self._config_service else 1.45
        strike = is_strike(self._current_pitch_observations, zone, radius_in)
        metrics = compute_plate_from_observations(self._current_pitch_observations)
        radar_speed = self._radar_client.latest_speed_mph() if self._manual_speed_mph is None else self._manual_speed_mph
        trajectory_result = None
        if self._current_pitch_observations:
            trajectory_request = TrajectoryFitRequest(
                observations=list(self._current_pitch_observations),
                plate_plane_z_ft=self._config.metrics.plate_plane_z_ft,
                radar_speed_mph=radar_speed,
                radar_speed_ref="release",
            )
            trajectory_result = self._trajectory_fitter.fit_trajectory(trajectory_request)
        crossing_xyz = trajectory_result.plate_crossing_xyz_ft if trajectory_result else None
        summary = PitchSummary(
            pitch_id=self._pitch_id,
            t_start_ns=self._pitch_start_ns,
            t_end_ns=self._pitch_end_ns,
            is_strike=strike.is_strike,
            zone_row=strike.zone_row,
            zone_col=strike.zone_col,
            run_in=metrics.run_in,
            rise_in=metrics.rise_in,
            speed_mph=radar_speed,
            rotation_rpm=None,
            sample_count=metrics.sample_count,
            trajectory_plate_x_ft=crossing_xyz[0] if crossing_xyz else None,
            trajectory_plate_y_ft=crossing_xyz[1] if crossing_xyz else None,
            trajectory_plate_z_ft=crossing_xyz[2] if crossing_xyz else None,
            trajectory_plate_t_ns=trajectory_result.plate_crossing_t_ns if trajectory_result else None,
            trajectory_model=trajectory_result.model_name if trajectory_result else None,
            trajectory_expected_error_ft=trajectory_result.expected_plate_error_ft if trajectory_result else None,
            trajectory_confidence=trajectory_result.confidence if trajectory_result else None,
        )
        self._session_pitches.append(summary)
        if self._current_pitch_observations:
            self._recent_pitch_paths.append(list(self._current_pitch_observations))
        self._last_session_summary = build_session_summary(
            self._record_session or "session",
            self._session_pitches,
        )
        self._current_pitch_observations = []
        self._write_pitch_manifest(summary)

    def _write_session_summary(self) -> None:
        if self._session_dir is None:
            return
        summary = self._last_session_summary
        path = self._session_dir / "session_summary.json"
        payload = asdict(summary)
        payload["schema_version"] = SCHEMA_VERSION
        payload["app_version"] = APP_VERSION
        path.write_text(json.dumps(payload, indent=2))
        self._write_session_summary_csv(summary)

    def _write_session_summary_csv(self, summary: SessionSummary) -> None:
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
                        f"{pitch.trajectory_expected_error_ft:.4f}" if pitch.trajectory_expected_error_ft is not None else "",
                        f"{pitch.trajectory_confidence:.3f}" if pitch.trajectory_confidence is not None else "",
                    ]
                )

    def _pitch_dir(self, pitch_id: str) -> Optional[Path]:
        if self._session_dir is None:
            return None
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in pitch_id)
        pitch_dir = self._session_dir / safe
        pitch_dir.mkdir(parents=True, exist_ok=True)
        return pitch_dir

    def _open_pitch_recording(self) -> None:
        if self._config is None:
            return
        pitch_dir = self._pitch_dir(self._pitch_id)
        if pitch_dir is None:
            return
        left_path = pitch_dir / "left.avi"
        right_path = pitch_dir / "right.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._pitch_left_writer = cv2.VideoWriter(
            str(left_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        self._pitch_right_writer = cv2.VideoWriter(
            str(right_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        left_csv = (pitch_dir / "left_timestamps.csv").open("w", newline="")
        right_csv = (pitch_dir / "right_timestamps.csv").open("w", newline="")
        self._pitch_left_csv = (left_csv, csv.writer(left_csv))
        self._pitch_right_csv = (right_csv, csv.writer(right_csv))
        self._pitch_left_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        self._pitch_right_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        self._pitch_post_end_ns = None
        self._pitch_latest_ns = {"left": 0, "right": 0}
        self._flush_pre_roll()

    def _close_pitch_recording(self, force: bool = False) -> None:
        with self._record_lock:
            if self._pitch_left_writer is not None:
                self._pitch_left_writer.release()
                self._pitch_left_writer = None
            if self._pitch_right_writer is not None:
                self._pitch_right_writer.release()
                self._pitch_right_writer = None
            if self._pitch_left_csv is not None:
                self._pitch_left_csv[0].close()
                self._pitch_left_csv = None
            if self._pitch_right_csv is not None:
                self._pitch_right_csv[0].close()
                self._pitch_right_csv = None
            if force:
                self._pitch_post_end_ns = None
                self._pitch_latest_ns = {"left": 0, "right": 0}

    def _buffer_pre_roll(self, label: str, frame: Frame) -> None:
        buffer = self._pre_roll_left if label == "left" else self._pre_roll_right
        buffer.append(frame)
        cutoff = frame.t_capture_monotonic_ns - self._pre_roll_ns
        while buffer and buffer[0].t_capture_monotonic_ns < cutoff:
            buffer.popleft()

    def _flush_pre_roll(self) -> None:
        for frame in list(self._pre_roll_left):
            self._write_pitch_frame("left", frame)
        for frame in list(self._pre_roll_right):
            self._write_pitch_frame("right", frame)

    def _write_pitch_frame(self, label: str, frame: Frame) -> None:
        if self._pitch_left_writer is None or self._pitch_right_writer is None:
            return
        image = frame.image
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        with self._record_lock:
            if label == "left" and self._pitch_left_writer is not None:
                self._pitch_left_writer.write(image)
                if self._pitch_left_csv is not None:
                    self._pitch_left_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
                self._pitch_latest_ns["left"] = frame.t_capture_monotonic_ns
            elif label == "right" and self._pitch_right_writer is not None:
                self._pitch_right_writer.write(image)
                if self._pitch_right_csv is not None:
                    self._pitch_right_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
                self._pitch_latest_ns["right"] = frame.t_capture_monotonic_ns
        self._maybe_close_pitch(frame.t_capture_monotonic_ns)

    def _maybe_close_pitch(self, frame_ns: int) -> None:
        if self._pitch_post_end_ns is None:
            return
        left_ns = self._pitch_latest_ns.get("left", 0)
        right_ns = self._pitch_latest_ns.get("right", 0)
        if left_ns >= self._pitch_post_end_ns and right_ns >= self._pitch_post_end_ns:
            self._close_pitch_recording()
            self._pitch_post_end_ns = None
            self._pitch_latest_ns = {"left": 0, "right": 0}

    def _write_pitch_manifest(self, summary: PitchSummary) -> None:
        pitch_dir = self._pitch_dir(summary.pitch_id)
        if pitch_dir is None:
            return
        config_path = str(self._config_path) if self._config_path else "configs/default.yaml"
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
            "config_path": config_path,
        }
        (pitch_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
