"""PipelineOrchestrator - Coordinates all services via EventBus.

This module provides the main pipeline orchestration that wires together
capture, detection, recording, and analysis services through EventBus.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Type

from app.contracts import CalibrationProfile, SessionSummary
from app.events.event_bus import EventBus
from app.events.event_types import (
    ObservationDetectedEvent,
    PitchEndEvent,
    PitchStartEvent,
    RayObservationDetectedEvent,
    StereoFrameProcessedEvent,
)
from app.pipeline.pitch_tracking_v2 import PitchConfig, PitchData, PitchStateMachineV2
from app.monitoring.error_budget import ErrorBudget, MetricLimit
from app.pipeline.service_contracts import PipelineService
from app.services.analysis import AnalysisServiceImpl
from app.services.capture import CaptureServiceImpl
from app.services.detection import DetectionServiceImpl
from app.services.recording import RecordingServiceImpl
from app.services.rig_profile import CRITICAL, RigProfile, RigProfileService
from calib.calibration_report import build_calibration_report
from configs.roi_io import load_runtime_roi_maps
from configs.settings import AppConfig
from contracts import Detection, Frame, StereoObservation
from contracts import (
    QualityAssessment,
    QUALITY_DEGRADED,
    QUALITY_ESTIMATED,
    QUALITY_REJECTED,
    QUALITY_UNAVAILABLE,
)
from detect.config import DetectorConfig as CvDetectorConfig
from detect.config import Mode
from log_config.logger import get_logger
from metrics.simple_metrics import PlateMetricsStub
from metrics.strike_zone import StrikeResult
from record.recorder import RecordingBundle

logger = get_logger(__name__)


class PipelineOrchestrator(PipelineService):
    """Event-driven pipeline orchestrator.

    Coordinates:
    - CaptureService: Camera management and frame acquisition
    - DetectionService: Object detection and stereo matching
    - RecordingService: Video recording and session management
    - AnalysisService: Pitch analysis and session summaries

    Architecture:
        EventBus (pub/sub)
        ├─ FrameCapturedEvent (from Capture)
        │   ├─> RecordingService (records frames)
        │   └─> DetectionService (detects objects)
        ├─ ObservationDetectedEvent (from Detection)
        │   ├─> RecordingService (records observations)
        │   └─> PipelineOrchestrator (feeds state machine)
        ├─ PitchStartEvent (from Orchestrator)
        │   └─> RecordingService (starts pitch recorder)
        └─ PitchEndEvent (from Orchestrator)
            ├─> RecordingService (finalizes pitch recorder)
            └─> AnalysisService (analyzes pitch)

    Thread Safety:
        - All public methods are thread-safe
        - EventBus handles synchronous event delivery
        - Services manage their own internal locking
    """

    def __init__(self, backend: str = "uvc"):
        """Initialize pipeline orchestrator.

        Args:
            backend: Camera backend ("uvc", "opencv", "sim")
        """
        self._backend = backend
        self._lock = threading.Lock()

        # EventBus (central coordination)
        self._event_bus = EventBus()

        # Services
        self._capture_service: Optional[CaptureServiceImpl] = None
        self._detection_service: Optional[DetectionServiceImpl] = None
        self._recording_service: Optional[RecordingServiceImpl] = None
        self._analysis_service: Optional[AnalysisServiceImpl] = None

        # Pitch tracking state machine
        self._pitch_config = PitchConfig()
        self._pitch_tracker: Optional[PitchStateMachineV2] = None

        # Configuration
        self._config: Optional[AppConfig] = None
        self._config_path: Optional[Path] = None
        self._record_dir: Optional[Path] = None
        self._manual_speed_mph: Optional[float] = None
        self._left_serial: Optional[str] = None
        self._right_serial: Optional[str] = None
        self._rig_profile_service = RigProfileService()
        self._active_rig_profile: Optional[RigProfile] = None
        self._runtime_calibration_path: Optional[Path] = None
        self._runtime_roi_path: Optional[Path] = None
        self._runtime_calibration_report: Optional[dict] = None

        # State
        self._capturing = False
        self._detection_started = False
        self._recording_active = False
        self._recording_paused = False

        # Latest observation for strike result
        self._latest_observation: Optional[StereoObservation] = None

        logger.info("PipelineOrchestrator initialized")

    # PipelineService Implementation

    def start_capture(
        self,
        config: AppConfig,
        left_serial: str,
        right_serial: str,
        config_path: Optional[Path] = None,
    ) -> None:
        """Start capture on both cameras.

        Args:
            config: Application configuration
            left_serial: Left camera serial number
            right_serial: Right camera serial number
            config_path: Optional path to config file

        Raises:
            RuntimeError: If capture already started
        """
        with self._lock:
            if self._capturing:
                raise RuntimeError("Capture already started")

            self._left_serial = left_serial
            self._right_serial = right_serial
            self._rig_profile_service = RigProfileService(config_path=Path(config_path) if config_path else Path("configs/default.yaml"))
            self._active_rig_profile = self._rig_profile_service.load_active_or_legacy(
                config,
                backend=self._backend,
                left_serial=left_serial,
                right_serial=right_serial,
            )
            validation = self._rig_profile_service.validate_for_runtime(
                self._active_rig_profile,
                config=config,
                backend=self._backend,
                left_serial=left_serial,
                right_serial=right_serial,
            )
            if validation.state == CRITICAL:
                logger.error(f"Rig profile runtime validation is CRITICAL: {validation.issues}")
                raise RuntimeError(
                    "Rig profile runtime validation is CRITICAL: "
                    + "; ".join(validation.issues or ["unknown validation failure"])
                )
            elif validation.warnings:
                logger.warning(f"Rig profile runtime validation warnings: {validation.warnings}")

            config = self._rig_profile_service.apply_profile_to_config(
                config,
                self._active_rig_profile,
                preserve_camera_mode=self._active_rig_profile.profile_id == "legacy",
            )
            self._runtime_calibration_path = self._rig_profile_service.calibration_path(self._active_rig_profile)
            self._runtime_roi_path = self._rig_profile_service.roi_path(self._active_rig_profile)
            self._runtime_calibration_report = build_calibration_report(
                self._runtime_calibration_path,
                Path(config_path) if config_path else Path("configs/default.yaml"),
            )

            # Store config
            self._config = config
            self._config_path = config_path

            # Create services if not exist
            if self._capture_service is None:
                self._capture_service = CaptureServiceImpl(self._event_bus, backend=self._backend)

            if self._detection_service is None:
                self._detection_service = DetectionServiceImpl(self._event_bus, config)
            else:
                self._detection_service.update_config(config)
            self._detection_service.set_runtime_calibration_path(self._runtime_calibration_path)
            self._apply_runtime_rois_to_detection(left_serial, right_serial)

            if self._recording_service is None:
                self._recording_service = RecordingServiceImpl(self._event_bus)
                if self._record_dir is not None:
                    self._recording_service.set_record_directory(self._record_dir)
                self._recording_service.set_manual_speed_mph(self._manual_speed_mph)
            self._recording_service.set_calibration_context(
                self._active_rig_profile.profile_id if self._active_rig_profile else None,
                self._runtime_calibration_report,
            )

            if self._analysis_service is None:
                self._analysis_service = AnalysisServiceImpl(self._event_bus, config)
                self._analysis_service.set_manual_speed_mph(self._manual_speed_mph)
            else:
                self._analysis_service.update_config(config)
                self._analysis_service.set_manual_speed_mph(self._manual_speed_mph)

            # Create pitch tracker from the active runtime configuration.
            self._pitch_config = PitchConfig(
                min_active_frames=config.recording.session_min_active_frames,
                end_gap_frames=config.recording.session_end_gap_frames,
                pre_roll_ms=float(config.recording.pre_roll_ms),
                frame_rate=float(config.camera.fps),
            )
            self._pitch_tracker = PitchStateMachineV2(self._pitch_config)
            self._pitch_tracker.set_callbacks(
                on_pitch_start=self._on_pitch_start_internal,
                on_pitch_end=self._on_pitch_end_internal,
            )

            # Subscribe to observation events
            self._subscribe_to_observations()

            # Start capture
            self._capture_service.start_capture(config, left_serial, right_serial)

            self._capturing = True
            logger.info("Capture started")

    def stop_capture(self) -> None:
        """Stop capture on both cameras.

        Thread-Safe: Can be called from any thread.
        Idempotent: Safe to call multiple times.
        """
        with self._lock:
            if not self._capturing:
                return

            # Stop capture
            if self._capture_service is not None:
                self._capture_service.stop_capture()

            # Stop detection if started
            if self._detection_started and self._detection_service is not None:
                self._detection_service.stop_detection()
                self._detection_started = False

            # Unsubscribe from events
            self._unsubscribe_from_observations()

            self._capturing = False
            logger.info("Capture stopped")

    def is_capturing(self) -> bool:
        """Check if capture is currently active.

        Returns:
            True if capture is active, False otherwise

        Thread-Safe: Can be called from any thread.
        """
        with self._lock:
            return self._capturing

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Return the latest frames for UI preview.

        Returns:
            Tuple of (left_frame, right_frame)

        Raises:
            RuntimeError: If capture not active
        """
        with self._lock:
            if self._capture_service is None or not self._capturing:
                raise RuntimeError("Capture not active")

            return self._capture_service.get_preview_frames()

    def start_recording(
        self,
        pitch_id: Optional[str] = None,
        session_name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """Begin recording frames and metadata.

        Args:
            pitch_id: Optional pitch identifier
            session_name: Optional session name
            mode: Optional recording mode

        Returns:
            Warning message if disk space is low, empty string otherwise

        Raises:
            RuntimeError: If capture not started
        """
        with self._lock:
            if not self._capturing:
                raise RuntimeError("Cannot start recording without capture")
            if self._recording_active:
                raise RuntimeError("Recording already active")

            if self._recording_service is None:
                raise RuntimeError("Recording service not initialized")

            detection_started_here = False
            analysis_started_here = False
            try:
                # Start detection if not already started
                if not self._detection_started and self._detection_service is not None:
                    # Configure detectors (use defaults from config)
                    self._detection_service.configure_detectors(
                        config=self._config.detector,
                        mode=Mode.MODE_A,
                        detector_type="classical",
                    )
                    self._detection_service.configure_threading(mode="per_camera", worker_count=2)
                    self._detection_service.start_detection()
                    self._detection_started = True
                    detection_started_here = True

                # Start analysis
                if self._analysis_service is not None:
                    self._analysis_service.start_analysis(session_id=session_name or "session")
                    analysis_started_here = True

                # Start recording service
                warning = self._recording_service.start_session(
                    session_name=session_name or "session",
                    config=self._config,
                    mode=mode,
                    pitch_id=pitch_id,
                    config_path=self._config_path,
                )
            except Exception:
                if analysis_started_here and self._analysis_service is not None:
                    try:
                        self._analysis_service.stop_analysis()
                    except Exception:
                        logger.exception("Failed to roll back analysis after recording start failure")
                if detection_started_here and self._detection_service is not None:
                    try:
                        self._detection_service.stop_detection()
                        self._detection_started = False
                    except Exception:
                        logger.exception("Failed to roll back detection after recording start failure")
                raise
            self._recording_active = True
            self._recording_paused = False
            return warning

    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for recordings.

        Args:
            path: Base directory path for recordings
        """
        with self._lock:
            self._record_dir = path
            if self._recording_service is not None:
                self._recording_service.set_record_directory(path)

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        """Set manual speed from external device.

        Args:
            speed_mph: Speed in mph (or None to clear)
        """
        with self._lock:
            self._manual_speed_mph = speed_mph
            if self._analysis_service is not None:
                self._analysis_service.set_manual_speed_mph(speed_mph)
            if self._recording_service is not None:
                self._recording_service.set_manual_speed_mph(speed_mph)

    def stop_recording(self) -> RecordingBundle:
        """Stop recording and return the bundle.

        Returns:
            RecordingBundle with session metadata

        Raises:
            RuntimeError: If recording not active
        """
        with self._lock:
            if self._recording_service is None:
                raise RuntimeError("Recording service not initialized")

            # Stop analysis
            if self._analysis_service is not None:
                self._analysis_service.stop_analysis()

            # Stop recording
            bundle = self._recording_service.stop_session()
            self._recording_active = False
            self._recording_paused = False

            logger.info(f"Recording stopped: {bundle.session_dir}")
            return bundle

    def pause_recording(self) -> None:
        """Pause active session recording while keeping capture live."""
        with self._lock:
            if not self._recording_active or self._recording_service is None:
                raise RuntimeError("Recording not active")
            if self._recording_paused:
                return

            if self._pitch_tracker is not None:
                self._pitch_tracker.force_end()

            if self._analysis_service is not None:
                self._analysis_service.pause_analysis()

            if self._detection_started and self._detection_service is not None:
                self._detection_service.stop_detection()
                self._detection_started = False

            self._recording_service.pause_session()
            self._recording_paused = True
            logger.info("Recording paused")

    def resume_recording(self) -> None:
        """Resume a paused recording session."""
        with self._lock:
            if not self._recording_active or self._recording_service is None:
                raise RuntimeError("Recording not active")
            if not self._recording_paused:
                return
            if self._detection_service is None:
                raise RuntimeError("Detection service not initialized")

            self._recording_service.resume_session()

            if self._analysis_service is not None:
                self._analysis_service.resume_analysis()

            self._detection_service.start_detection()
            self._detection_started = True
            self._recording_paused = False
            logger.info("Recording resumed")

    def is_recording_paused(self) -> bool:
        """Check if the current recording session is paused."""
        with self._lock:
            return self._recording_paused

    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        """Reject runtime calibration and point callers to setup tooling.

        Args:
            profile_id: Calibration profile identifier

        Returns:
            CalibrationProfile with metadata

        Raises:
            NotImplementedError: Calibration is intentionally owned by setup
                tooling for the pilot runtime.
        """
        message = (
            "Calibration is not run by PipelineOrchestrator in v1.5.0-pilot. "
            "Use Setup Doctor or app.services.tooling.SubprocessToolingService "
            "to create and validate the rig profile, then start capture with "
            "that validated profile. The orchestrator owns runtime capture, "
            "recording, detection, and analysis only."
        )
        logger.warning("run_calibration(%s) rejected: %s", profile_id, message)
        raise NotImplementedError(message)

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Return capture stats for both cameras.

        Returns:
            Dict mapping camera_id to stats dict
        """
        with self._lock:
            if self._capture_service is None:
                return {}

            return self._capture_service.get_stats()

    def get_quality_diagnostics(self) -> dict:
        """Return detailed runtime evidence without placing it on the default UI."""
        with self._lock:
            capture = self._capture_service.get_stats() if self._capture_service else {}
            detection_service = self._detection_service
            recording_service = self._recording_service
            analysis_service = self._analysis_service
            profile = self._active_rig_profile
            calibration_report = dict(self._runtime_calibration_report or {})

        detection = detection_service.get_quality_diagnostics() if detection_service else {}
        recording = dict(recording_service.get_frame_writer_stats()) if recording_service else {}
        analysis = dict(analysis_service.get_worker_stats()) if analysis_service else {}
        recording_drop = _rate_evidence(
            recording.get("dropped", 0),
            recording.get("submitted", 0) + recording.get("dropped", 0),
        )
        recording_failure = _rate_evidence(recording.get("failed", 0), recording.get("submitted", 0))
        analysis_drop = _rate_evidence(
            analysis.get("dropped", 0),
            analysis.get("submitted", 0) + analysis.get("dropped", 0),
        )
        analysis_failure = _rate_evidence(analysis.get("failed", 0), analysis.get("submitted", 0))
        recording.update(
            drop_rate=recording_drop["value"],
            drop_rate_evidence=recording_drop,
            failure_rate=recording_failure["value"],
            failure_rate_evidence=recording_failure,
        )
        analysis.update(
            drop_rate=analysis_drop["value"],
            drop_rate_evidence=analysis_drop,
            failure_rate=analysis_failure["value"],
            failure_rate_evidence=analysis_failure,
        )
        pair_rates = (detection.get("pair_outcomes") or {}).get("rejection_rates") or {}
        metrics = {
            "detection_loss_rate": (detection.get("detection_loss") or {}).get("value"),
            "recording_drop_rate": recording.get("drop_rate"),
            "recording_failure_rate": recording.get("failure_rate"),
            "analysis_drop_rate": analysis.get("drop_rate"),
            "analysis_failure_rate": analysis.get("failure_rate"),
            "pair_skew_p95_ms": (detection.get("sync") or {}).get("p95_delta_ms"),
            "tracklet_start_rate": (detection.get("detection") or {}).get("tracklet_start_rate"),
            "pair_skew_rejection_rate": pair_rates.get("PAIR_SKEW_OUT_OF_TOLERANCE"),
            "association_rejection_rate": pair_rates.get("NO_VALID_STEREO_ASSOCIATION"),
        }
        budget = _runtime_error_budget(profile)
        budget_assessment = budget.assess("session", metrics, assessment_id="runtime-current")
        reasons = list(budget_assessment.reason_codes)
        status = budget_assessment.status
        sync_quality = str((detection.get("sync") or {}).get("sync_quality") or "UNKNOWN")
        if sync_quality == "POOR":
            status = QUALITY_REJECTED
            reasons.append("STEREO_SYNC_POOR")
        elif sync_quality == "WARN" and status not in {QUALITY_REJECTED, QUALITY_UNAVAILABLE}:
            status = QUALITY_DEGRADED
            reasons.append("STEREO_SYNC_WARN")
        elif sync_quality == "UNKNOWN" and status != QUALITY_REJECTED:
            status = QUALITY_UNAVAILABLE
            reasons.append("STEREO_SYNC_UNKNOWN")
        drift_state = str((detection.get("drift") or {}).get("state") or "PASS")
        if drift_state == "FAIL":
            status = QUALITY_REJECTED
            reasons.append("RIG_DRIFT_FAIL")
        elif drift_state == "WARN" and status != QUALITY_REJECTED:
            status = QUALITY_DEGRADED
            reasons.append("RIG_DRIFT_WARN")
        assessment = QualityAssessment(
            assessment_id="runtime-current",
            scope="session",
            status=status,
            reason_codes=reasons,
            metrics=metrics,
            thresholds=budget_assessment.thresholds,
            recommendations=["Open diagnostics and rerun the failing setup check."] if reasons else [],
            diagnostics=budget_assessment.diagnostics,
        )
        return {
            "quality": assessment.to_payload(),
            "rig_profile_id": profile.profile_id if profile else None,
            "capture": capture,
            "detection": detection,
            "recording": recording,
            "analysis": analysis,
            "calibration": calibration_report,
        }
    def get_plate_metrics(self) -> PlateMetricsStub:
        """Return latest plate-gated metrics (stubbed if unavailable).

        Returns:
            PlateMetricsStub with plate crossing statistics
        """
        with self._lock:
            if self._analysis_service is None:
                return PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)

            return self._analysis_service.get_plate_metrics()

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
        """Update detector configuration for the active session.

        Args:
            config: CV detector configuration
            mode: Detection mode (MODE_A or MODE_B)
            detector_type: "classical" or "ml"
            model_path: Path to ML model (if detector_type="ml")
            model_input_size: Model input dimensions
            model_conf_threshold: Confidence threshold
            model_class_id: Class ID to detect
            model_format: Model format ("yolo_v5", "yolo_v8", etc.)
        """
        with self._lock:
            if self._detection_service is None:
                return

            self._detection_service.configure_detectors(
                config=config,
                mode=mode,
                detector_type=detector_type,
                model_path=model_path,
                model_input_size=model_input_size,
                model_conf_threshold=model_conf_threshold,
                model_class_id=model_class_id,
                model_format=model_format,
            )

    def set_detection_threading(self, mode: str, worker_count: int) -> None:
        """Set detection threading mode.

        Args:
            mode: "per_camera" or "worker_pool"
            worker_count: Number of worker threads
        """
        with self._lock:
            if self._detection_service is None:
                return

            self._detection_service.configure_threading(mode, worker_count)

    def get_latest_detections(self) -> Dict[str, List[Detection]]:
        """Return latest raw detections by camera id.

        Returns:
            Dict mapping camera_id to list of detections
        """
        with self._lock:
            if self._detection_service is None:
                return {}

            return self._detection_service.get_latest_detections()

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, List[Detection]]]:
        """Return latest gated detections by camera id and gate name.

        Returns:
            Dict mapping camera_id to dict of gate_name to filtered detections
        """
        with self._lock:
            if self._detection_service is None:
                return {}

            return self._detection_service.get_latest_gated_detections()

    def get_strike_result(self) -> StrikeResult:
        """Return latest strike determination.

        Returns:
            StrikeResult with strike determination and zone location
        """
        with self._lock:
            if self._analysis_service is None or self._latest_observation is None:
                # Return default "ball" result
                from metrics.strike_zone import StrikeResult

                return StrikeResult(is_strike=False, sample_count=0, zone_row=None, zone_col=None)

            return self._analysis_service.calculate_strike_result(
                self._latest_observation,
                self._config,
            )

    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type for strike detection.

        Args:
            ball_type: "baseball" or "softball"
        """
        with self._lock:
            if self._analysis_service is not None:
                self._analysis_service.set_ball_type(ball_type)

    def set_batter_height_in(self, height_in: float) -> None:
        """Set batter height for strike zone calculation.

        Args:
            height_in: Batter height in inches

        Raises:
            ValueError: If height is outside valid range (36-84 inches)
        """
        with self._lock:
            if self._analysis_service is not None:
                self._analysis_service.set_batter_height_in(height_in)

    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        """Set strike zone top/bottom ratios for the active session.

        Args:
            top_ratio: Top of zone as fraction of batter height
            bottom_ratio: Bottom of zone as fraction of batter height

        Raises:
            ValueError: If ratios are invalid
        """
        with self._lock:
            if self._analysis_service is not None:
                self._analysis_service.set_strike_zone_ratios(top_ratio, bottom_ratio)

    def get_session_summary(self) -> SessionSummary:
        """Return the latest session summary.

        Returns:
            SessionSummary with current session statistics
        """
        with self._lock:
            if self._analysis_service is None:
                return SessionSummary(
                    session_id="none",
                    pitch_count=0,
                    strikes=0,
                    balls=0,
                    heatmap=[[0] * 3 for _ in range(3)],
                    pitches=[],
                )

            return self._analysis_service.get_session_summary()

    def get_recent_pitch_paths(self) -> List[List[StereoObservation]]:
        """Return recent pitch observation paths.

        Returns:
            List of pitch paths (each path is list of observations)
        """
        with self._lock:
            if self._analysis_service is None:
                return []

            return self._analysis_service.get_recent_pitch_paths()

    def get_recent_pitches(self, count: int = 10) -> List:
        """Return the most recent analyzed pitches for coaching UI compatibility."""
        summary = self.get_session_summary()
        return list(summary.pitches[-count:])

    def get_session_dir(self) -> Optional[Path]:
        """Return the current session directory if available.

        Returns:
            Path to current session directory, or None if not recording
        """
        with self._lock:
            if self._recording_service is None:
                return None

            return self._recording_service.get_session_dir()

    def get_last_session_summary(self) -> SessionSummary:
        """Compatibility wrapper for UI callers that expect the legacy API."""
        return self.get_session_summary()

    def reload_config(self, config: AppConfig) -> None:
        """Reload configuration for future analysis and recording operations."""
        with self._lock:
            self._config = config
            if self._analysis_service is not None:
                self._analysis_service.update_config(config)
            if self._detection_service is not None:
                self._detection_service.update_config(config)

    def reload_rois(self) -> None:
        """Reload ROIs from the active rig profile or legacy fallback."""
        with self._lock:
            if self._detection_service is None:
                return
            left_serial = self._left_serial or "left"
            right_serial = self._right_serial or "right"
            if self._active_rig_profile is None and self._config is not None:
                self._active_rig_profile = self._rig_profile_service.load_active_or_legacy(
                    self._config,
                    backend=self._backend,
                    left_serial=left_serial,
                    right_serial=right_serial,
                )
                self._runtime_roi_path = self._rig_profile_service.roi_path(self._active_rig_profile)
            self._apply_runtime_rois_to_detection(left_serial, right_serial)

    def update_mound_distance(self, distance_ft: float) -> None:
        """Update mound distance in the active configuration."""
        with self._lock:
            if self._config is None:
                return

            self._config = replace(
                self._config,
                metrics=replace(self._config.metrics, release_plane_z_ft=distance_ft),
            )
            if self._analysis_service is not None:
                self._analysis_service.update_config(self._config)

    # Internal Event Handlers

    def _on_observation_detected_internal(self, event: ObservationDetectedEvent) -> None:
        """Handle ObservationDetectedEvent from EventBus.

        Feeds observations to pitch state machine and updates strike result.

        Args:
            event: ObservationDetectedEvent with stereo observation

        Note: Called from publisher's thread (DetectionService)
        """
        try:
            observation = self._to_field_coordinates(event.observation)
            # Store latest field-frame observation for strike result.
            self._latest_observation = observation

            # Store the observation. Lifecycle timing is driven exactly once
            # per stereo pair by StereoFrameProcessedEvent.
            if self._pitch_tracker is not None:
                self._pitch_tracker.add_observation(observation)

        except Exception as e:
            logger.error(f"Error handling observation: {e}", exc_info=True)

    def _to_field_coordinates(self, observation: StereoObservation) -> StereoObservation:
        """Apply the active rig's validated camera-to-field transform."""
        if self._active_rig_profile is None:
            return observation
        matrix = (self._active_rig_profile.field_transform or {}).get("matrix_4x4")
        if not matrix:
            return observation
        point = (observation.X, observation.Y, observation.Z, 1.0)
        transformed = [sum(float(matrix[row][col]) * point[col] for col in range(4)) for row in range(3)]
        covariance = observation.covariance
        transformed_covariance = covariance
        if covariance is not None:
            rotation = [[float(matrix[row][col]) for col in range(3)] for row in range(3)]
            rotated = [
                [
                    sum(
                        rotation[row][i] * float(covariance[i][j]) * rotation[col][j]
                        for i in range(3)
                        for j in range(3)
                    )
                    for col in range(3)
                ]
                for row in range(3)
            ]
            transformed_covariance = tuple(tuple(value for value in row) for row in rotated)
        return replace(
            observation,
            X=transformed[0],
            Y=transformed[1],
            Z=transformed[2],
            covariance=transformed_covariance,
        )

    def _ray_modes_enabled(self) -> bool:
        if self._config is None or getattr(self._config, "trajectory", None) is None:
            return False
        modes = [self._config.trajectory.primary_mode, *self._config.trajectory.compare_modes]
        return any(mode.startswith("ray_") for mode in modes)

    def _ray_modes_drive_pitch(self) -> bool:
        return bool(
            self._config is not None
            and getattr(self._config, "trajectory", None) is not None
            and self._config.trajectory.primary_mode.startswith("ray_")
        )

    def _on_ray_observation_detected_internal(self, event: RayObservationDetectedEvent) -> None:
        """Handle per-camera ray observations when ray trajectory modes are enabled."""
        try:
            if not self._ray_modes_enabled() or self._pitch_tracker is None:
                return

            self._pitch_tracker.add_ray_observation(event.observation)
        except Exception as e:
            logger.error(f"Error handling ray observation: {e}", exc_info=True)

    def _on_stereo_frame_processed_internal(self, event: StereoFrameProcessedEvent) -> None:
        """Advance pitch lifecycle exactly once for each processed pair."""
        try:
            if self._pitch_tracker is None:
                return
            self._pitch_tracker.update(
                frame_ns=event.timestamp_ns,
                lane_count=event.lane_count,
                plate_count=event.plate_count,
                obs_count=len(event.observations),
            )
        except Exception as e:
            logger.error(f"Error handling stereo frame pair: {e}", exc_info=True)

    def _on_pitch_start_internal(self, pitch_index: int, pitch_data: PitchData) -> None:
        """Handle pitch start from state machine.

        Publishes PitchStartEvent to EventBus.

        Args:
            pitch_index: Pitch index
            pitch_data: Pitch data snapshot

        Note: Called from state machine (detection thread)
        """
        try:
            # Publish PitchStartEvent
            event = PitchStartEvent(
                pitch_id=self._make_pitch_id(pitch_index),
                pitch_index=pitch_index,
                timestamp_ns=pitch_data.start_ns,
            )
            self._event_bus.publish(event)

            logger.info(f"Pitch started: {pitch_index}")

        except Exception as e:
            logger.error(f"Error handling pitch start: {e}", exc_info=True)

    def _on_pitch_end_internal(self, pitch_data: PitchData) -> None:
        """Handle pitch end from state machine.

        Publishes PitchEndEvent to EventBus.

        Args:
            pitch_data: Finalized pitch data

        Note: Called from state machine (detection thread)
        """
        try:
            # Publish PitchEndEvent
            event = PitchEndEvent(
                pitch_id=self._make_pitch_id(pitch_data.pitch_index),
                observations=pitch_data.observations,
                timestamp_ns=pitch_data.end_ns,
                duration_ns=pitch_data.duration_ns(),
                ray_observations=pitch_data.ray_observations,
                coordinate_frame=(
                    "field"
                    if self._active_rig_profile and self._active_rig_profile.field_transform.get("matrix_4x4")
                    else "camera"
                ),
                rig_profile_id=self._active_rig_profile.profile_id if self._active_rig_profile else None,
            )
            self._event_bus.publish(event)

            logger.info(f"Pitch ended: {pitch_data.pitch_index}, {len(pitch_data.observations)} observations")

        except Exception as e:
            logger.error(f"Error handling pitch end: {e}", exc_info=True)

    # EventBus Subscription Management

    def _subscribe_to_observations(self) -> None:
        """Subscribe to ObservationDetectedEvent from EventBus."""
        self._event_bus.subscribe(ObservationDetectedEvent, self._on_observation_detected_internal)
        self._event_bus.subscribe(RayObservationDetectedEvent, self._on_ray_observation_detected_internal)
        self._event_bus.subscribe(StereoFrameProcessedEvent, self._on_stereo_frame_processed_internal)
        logger.info("PipelineOrchestrator subscribed to ObservationDetectedEvent")

    def _unsubscribe_from_observations(self) -> None:
        """Unsubscribe from ObservationDetectedEvent."""
        self._event_bus.unsubscribe(ObservationDetectedEvent, self._on_observation_detected_internal)
        self._event_bus.unsubscribe(RayObservationDetectedEvent, self._on_ray_observation_detected_internal)
        self._event_bus.unsubscribe(StereoFrameProcessedEvent, self._on_stereo_frame_processed_internal)
        logger.info("PipelineOrchestrator unsubscribed from ObservationDetectedEvent")

    def subscribe_event(self, event_type: Type, handler: Callable) -> None:
        """Register a public EventBus subscription without exposing internals."""
        self._event_bus.subscribe(event_type, handler)

    def unsubscribe_event(self, event_type: Type, handler: Callable) -> bool:
        """Remove a public EventBus subscription without exposing internals."""
        return self._event_bus.unsubscribe(event_type, handler)

    @staticmethod
    def _make_pitch_id(pitch_index: int) -> str:
        return f"pitch_{pitch_index:05d}"

    def _apply_runtime_rois_to_detection(self, left_serial: str, right_serial: str) -> None:
        if self._detection_service is None or self._runtime_roi_path is None:
            return

        lane_by_serial, plate_by_serial = load_runtime_roi_maps(
            self._runtime_roi_path,
            left_serial,
            right_serial,
            lane_path=Path("rois/shared_lane_rois.json"),
        )
        lane_rois = _serial_roi_map_to_camera_ids(lane_by_serial, left_serial, right_serial)
        plate_rois = _serial_roi_map_to_camera_ids(plate_by_serial, left_serial, right_serial)
        if not lane_rois and not plate_rois:
            logger.warning(f"No runtime ROIs loaded from {self._runtime_roi_path}")
            return
        self._detection_service.set_lane_rois(lane_rois, plate_rois or None)
        logger.info(
            f"Runtime ROIs loaded from {self._runtime_roi_path} "
            f"(lane={sorted(lane_rois.keys())}, plate={sorted(plate_rois.keys())})"
        )


def _serial_roi_map_to_camera_ids(
    roi_map: Dict[str, List[Tuple[float, float]]],
    left_serial: str,
    right_serial: str,
) -> Dict[str, List[Tuple[float, float]]]:
    left = roi_map.get("left") or roi_map.get(left_serial)
    right = roi_map.get("right") or roi_map.get(right_serial)
    output: Dict[str, List[Tuple[float, float]]] = {}
    if left is not None:
        output[left_serial] = list(left)
    if right is not None:
        output[right_serial] = list(right)
    return output


def _runtime_error_budget(profile: Optional[RigProfile]) -> ErrorBudget:
    raw = profile.error_budget if profile is not None else {}
    raw_limits = raw.get("limits") or {}
    limits: dict[str, MetricLimit] = {
        "detection_loss_rate": MetricLimit(0.001, 0.01, "ratio"),
        "recording_drop_rate": MetricLimit(0.001, 0.01, "ratio"),
        "recording_failure_rate": MetricLimit(0.0, 0.01, "ratio"),
        "analysis_drop_rate": MetricLimit(0.0, 0.01, "ratio"),
        "analysis_failure_rate": MetricLimit(0.0, 0.01, "ratio"),
        "pair_skew_p95_ms": MetricLimit(0.5, 1.0, "ms"),
        "tracklet_start_rate": MetricLimit(0.5, 0.8, "ratio"),
        "pair_skew_rejection_rate": MetricLimit(0.01, 0.05, "ratio"),
        "association_rejection_rate": MetricLimit(0.2, 0.5, "ratio"),
    }
    for name, descriptor in raw_limits.items():
        try:
            limits[name] = MetricLimit(
                warn=float(descriptor["warn"]),
                reject=float(descriptor["reject"]),
                units=str(descriptor.get("units") or ""),
            )
        except (KeyError, TypeError, ValueError):
            logger.warning("Ignoring malformed runtime error-budget limit: %s", name)
    return ErrorBudget(
        budget_id=str(raw.get("budget_id") or "runtime-default-v2"),
        version=str(raw.get("version") or "2"),
        limits=limits,
    )


def _rate_evidence(numerator: object, denominator: object) -> dict:
    """Return an auditable rate, preserving zero opportunity as unavailable."""
    try:
        numerator_value = int(numerator)
        denominator_value = int(denominator)
    except (TypeError, ValueError):
        return {"numerator": numerator, "denominator": denominator, "value": None}
    return {
        "numerator": numerator_value,
        "denominator": denominator_value,
        "value": numerator_value / denominator_value if denominator_value > 0 else None,
    }
