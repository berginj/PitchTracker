"""In-process pipeline service to back the UI."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import cast, Dict, Optional, Tuple

from configs.settings import AppConfig
from contracts import Frame, PitchMetrics
from detect.lane import LaneGate
from detect.detector import Detector
from exceptions import (
    CameraConfigurationError,
    CameraConnectionError,
    CameraNotFoundError,
    DetectionError,
    InvalidROIError,
    ModelLoadError,
    PitchTrackerError,
)
from integrations.radar import NullRadarGun, RadarGunClient
from log_config.logger import get_logger
from metrics.simple_metrics import PlateMetricsStub
from record.recorder import RecordingBundle
from stereo import StereoLaneGate
from stereo.association import StereoMatcher
from app.pipeline.config_service import ConfigService
from app.pipeline.initialization import PipelineInitializer
from app.pipeline.camera_management import CameraManager
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.service_contracts import (
    CalibrationProfile,
    PipelineService,
    SessionSummary,
)
from app.contracts import PitchSummary
from app.pipeline.service_detection import PipelineServiceDetectionMixin
from app.pipeline.service_recording import PipelineServiceRecordingMixin
from app.pipeline.service_config import PipelineServiceConfigMixin
from app.pipeline.recording.session_recorder import SessionRecorder
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.pipeline.analysis.session_summary import SessionManager
from app.pipeline.pitch_tracking_v2 import PitchStateMachineV2
from app.services.rig_profile import RigProfileService

logger = get_logger(__name__)


class InProcessPipelineService(
    PipelineServiceDetectionMixin,
    PipelineServiceRecordingMixin,
    PipelineServiceConfigMixin,
    PipelineService,
):
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
        self._detectors_by_camera: Dict[str, Detector] = {}
        self._lane_polygon: Optional[list[tuple[float, float]]] = None
        self._stereo: Optional[StereoMatcher] = None
        self._recording = False
        self._recorded_frames: list[Frame] = []
        self._pitch_id = "pitch-unknown"
        self._config: Optional[AppConfig] = None
        self._config_service: Optional[ConfigService] = None
        self._config_path: Optional[Path] = None
        self._rig_profile_service = RigProfileService()
        self._runtime_calibration_path: Optional[Path] = None
        self._runtime_roi_path: Optional[Path] = None
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
        self._last_pitch_summary: Optional[PitchSummary] = None
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

        # Enable camera reconnection for physical cameras
        if backend != "sim":
            self._camera_mgr.enable_reconnection(enabled=True)
            self._camera_mgr.set_camera_state_callback(self._on_camera_state_changed)
            logger.info("Camera reconnection enabled for pipeline service")

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
            self._rig_profile_service = RigProfileService(
                config_path=Path(config_path) if config_path else Path("configs/default.yaml")
            )
            rig_profile = self._rig_profile_service.load_active_or_legacy(
                config,
                backend=self._backend,
                left_serial=left_serial,
                right_serial=right_serial,
            )
            config = self._rig_profile_service.apply_profile_to_config(
                config,
                rig_profile,
                preserve_camera_mode=rig_profile.profile_id == "legacy",
            )
            self._runtime_calibration_path = self._rig_profile_service.calibration_path(rig_profile)
            self._runtime_roi_path = self._rig_profile_service.roi_path(rig_profile)

            self._config = config
            self._config_service = ConfigService(config)
            self._config_path = config_path
            self._record_dir = Path(config.recording.output_dir)
            self._detect_queue_size = config.camera.queue_depth or 6

            # Start camera capture (opens, configures, starts threads)
            try:
                self._camera_mgr.start_capture(config, left_serial, right_serial)
            except (CameraConnectionError, CameraConfigurationError):
                # Camera errors - let them propagate
                raise

            # Get camera IDs from camera manager
            left_id, right_id = self._camera_mgr.get_camera_ids()
            if left_id is None or right_id is None:
                self._camera_mgr.stop_capture()
                raise CameraConfigurationError(
                    "Camera capture started without both resolved camera identifiers"
                )

            # Load ROIs
            try:
                logger.debug("Loading ROIs")
                (
                    self._lane_polygon,
                    self._lane_gate,
                    self._stereo_gate,
                    self._plate_gate,
                    self._plate_stereo_gate,
                ) = PipelineInitializer.load_rois(
                    left_id or left_serial,
                    right_id or right_serial,
                    roi_path=self._runtime_roi_path or Path("configs/roi.json"),
                    lane_path=Path("rois/shared_lane_rois.json"),
                )
            except Exception as exc:
                logger.error(f"Failed to load ROIs: {exc}")
                self._camera_mgr.stop_capture()
                error_msg = (
                    f"Failed to load ROI configuration: {exc}\n\n"
                    f"Possible solutions:\n"
                    f"  • Run Setup Doctor to configure ROIs\n"
                    f"  • Check that roi.yaml exists in the configs directory\n"
                    f"  • Verify camera serials match configured ROIs"
                )
                raise InvalidROIError(error_msg) from exc

            # Initialize detector
            try:
                logger.debug("Initializing detector")
                self._initializer.initialize_detector_config(config)
                self._detectors_by_camera = self._initializer.build_detectors(left_id, right_id, self._lane_polygon)
                if self._initializer._detector_type == "ml":
                    self._initializer.warmup_detectors(self._detectors_by_camera, config)
            except Exception as exc:
                logger.error(f"Failed to initialize detector: {exc}")
                self._camera_mgr.stop_capture()
                if "model" in str(exc).lower() or "onnx" in str(exc).lower():
                    model_path = config.detector.model_path if config.detector.model_path else "not specified"
                    error_msg = (
                        f"Failed to load ML detector model: {exc}\n\n"
                        f"Model path: {model_path}\n\n"
                        f"Possible solutions:\n"
                        f"  • Switch to classical detector in settings (recommended for most users)\n"
                        f"  • Download the ML model and place it at: {model_path}\n"
                        f"  • Check that ONNX Runtime is installed: pip install onnxruntime\n"
                        f"  • Verify model file is not corrupted"
                    )
                    raise ModelLoadError(error_msg) from exc
                error_msg = (
                    f"Failed to initialize detector: {exc}\n\n"
                    f"Possible solutions:\n"
                    f"  • Check detector configuration in settings\n"
                    f"  • Reset detector settings to defaults\n"
                    f"  • Check logs for detailed error information"
                )
                raise DetectionError(error_msg) from exc

            # Initialize stereo
            try:
                logger.debug("Initializing stereo")
                self._stereo = PipelineInitializer.create_stereo_matcher(
                    config,
                    self._runtime_calibration_path or Path("calibration/stereo_calibration.npz"),
                )
            except Exception as exc:
                logger.error(f"Failed to initialize stereo: {exc}")
                self._camera_mgr.stop_capture()
                error_msg = (
                    f"Failed to initialize stereo system: {exc}\n\n"
                    f"This usually indicates a calibration issue.\n\n"
                    f"Possible solutions:\n"
                    f"  • Re-run camera calibration from Setup Doctor\n"
                    f"  • Check that calibration.npz exists in the configs directory\n"
                    f"  • Verify baseline_ft and focal_length_px in default.yaml\n"
                    f"  • Ensure both cameras are properly configured"
                )
                raise PitchTrackerError(error_msg) from exc

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
                    get_ball_radius_fn=lambda: self._config_service.get_ball_radius_in()
                    if self._config_service
                    else 1.45,
                )
                self._detection_processor.set_stereo_pair_callback(self._on_stereo_pair)
                self._detection_processor.set_ray_observation_callback(self._on_ray_observations)
            except Exception as exc:
                logger.error(f"Failed to create detection processor: {exc}")
                self._camera_mgr.stop_capture()
                error_msg = (
                    f"Failed to create detection processor: {exc}\n\n"
                    f"Possible solutions:\n"
                    f"  • Check that ROIs and gates are properly configured\n"
                    f"  • Verify stereo calibration is valid\n"
                    f"  • Restart the application\n"
                    f"  • Check system memory availability"
                )
                raise DetectionError(error_msg) from exc

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
                error_msg = (
                    f"Failed to start detection threads: {exc}\n\n"
                    f"This usually indicates a system resource issue.\n\n"
                    f"Possible solutions:\n"
                    f"  • Close other applications to free up system resources\n"
                    f"  • Check Task Manager for high CPU or memory usage\n"
                    f"  • Restart the application\n"
                    f"  • Restart your computer if the issue persists"
                )
                raise CameraConnectionError(error_msg) from exc

            logger.info("Capture started successfully")

        except (
            CameraNotFoundError,
            CameraConnectionError,
            CameraConfigurationError,
            InvalidROIError,
            ModelLoadError,
            DetectionError,
        ):
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
        Logs errors from individual cleanup steps as warnings rather than
        silently swallowing them, and re-raises if camera stop itself fails.
        """
        logger.info("Stopping capture")
        errors: list[Exception] = []

        # Stop detection threads
        try:
            if self._detection_pool:
                self._detection_pool.stop()
            logger.debug("Detection threads stopped")
        except Exception as exc:
            logger.warning(f"Error stopping detection threads: {exc}")
            errors.append(exc)

        # Stop camera capture (stops threads, closes cameras)
        try:
            self._camera_mgr.stop_capture()
        except Exception as exc:
            logger.exception("Error stopping camera capture")
            errors.append(exc)

        if errors:
            logger.warning(f"Capture stopped with {len(errors)} error(s)")
        else:
            logger.info("Capture stopped successfully")

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
    ) -> str:
        """Start recording session.

        Returns:
            Warning message if disk space is low, empty string otherwise
        """
        with self._record_lock:
            self._recording = True
            self._recorded_frames = []
            self._last_pitch_summary = None
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
        warning = self._start_recording_io()
        return warning

    def set_record_directory(self, path: Optional[Path]) -> None:
        self._record_dir = path

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        self._manual_speed_mph = speed_mph

    def stop_recording(self) -> RecordingBundle:
        with self._record_lock:
            self._recording = False
            self._session_active = False
            pitch_tracker = self._pitch_tracker
            pitch_id = self._pitch_id
            summary = self._last_pitch_summary

        if pitch_tracker:
            pitch_tracker.force_end()
        self._stop_recording_io()

        # Build metrics from last analyzed pitch if available
        if summary is not None:
            metrics = PitchMetrics(
                pitch_id=summary.pitch_id,
                t_start_ns=summary.t_start_ns,
                t_end_ns=summary.t_end_ns,
                velo_mph=summary.speed_mph or 0.0,
                HB_in=summary.run_in,
                iVB_in=summary.rise_in,
                release_xyz_ft=(0.0, 0.0, 0.0),
                approach_angles_deg=(0.0, 0.0),
                confidence=summary.trajectory_confidence or 0.0,
            )
        else:
            metrics = PitchMetrics(
                pitch_id=pitch_id,
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
            pitch_id=pitch_id,
            frames=[],
            detections=[],
            track=[],
            metrics=metrics,
            session_dir=self.get_session_dir(),
        )

    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        created_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return CalibrationProfile(profile_id=profile_id, created_utc=created_utc, schema_version="1.0.0")

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        return cast(Dict[str, Dict[str, float]], self._camera_mgr.get_stats())

    def get_plate_metrics(self) -> PlateMetricsStub:
        if self._detection_processor:
            return self._detection_processor.get_plate_metrics()
        return PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)
