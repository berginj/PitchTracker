"""PipelineOrchestrator - Coordinates all services via EventBus.

This module provides the main pipeline orchestration that wires together
capture, detection, recording, and analysis services through EventBus.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    ObservationDetectedEvent,
    PitchEndEvent,
    PitchStartEvent,
)
from app.pipeline.pitch_tracking_v2 import PitchConfig, PitchData, PitchStateMachineV2
from app.pipeline_service import CalibrationProfile, PipelineService, SessionSummary
from app.services.analysis import AnalysisServiceImpl
from app.services.capture import CaptureServiceImpl
from app.services.detection import DetectionServiceImpl
from app.services.recording import RecordingServiceImpl
from configs.settings import AppConfig
from contracts import Detection, Frame, StereoObservation
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

        # State
        self._capturing = False
        self._detection_started = False

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

            # Store config
            self._config = config
            self._config_path = config_path

            # Create services if not exist
            if self._capture_service is None:
                self._capture_service = CaptureServiceImpl(self._event_bus, backend=self._backend)

            if self._detection_service is None:
                self._detection_service = DetectionServiceImpl(self._event_bus, config)

            if self._recording_service is None:
                self._recording_service = RecordingServiceImpl(self._event_bus)

            if self._analysis_service is None:
                self._analysis_service = AnalysisServiceImpl(self._event_bus, config)

            # Create pitch tracker
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

            if self._recording_service is None:
                raise RuntimeError("Recording service not initialized")

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

            # Start analysis
            if self._analysis_service is not None:
                self._analysis_service.start_analysis()

            # Start recording service
            return self._recording_service.start_session(
                session_name=session_name or "session",
                config=self._config,
                mode=mode,
            )

    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for recordings.

        Args:
            path: Base directory path for recordings
        """
        with self._lock:
            if self._recording_service is not None:
                self._recording_service.set_record_directory(path)

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        """Set manual speed from external device.

        Args:
            speed_mph: Speed in mph (or None to clear)

        Note: Not implemented in current architecture
        """
        # TODO: Implement manual speed override if needed
        pass

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

            logger.info(f"Recording stopped: {bundle.session_dir}")
            return bundle

    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        """Run calibration and return a profile summary.

        Args:
            profile_id: Calibration profile identifier

        Returns:
            CalibrationProfile with metadata

        Note: Calibration runs in separate calibration pipeline
        """
        # TODO: Implement calibration via separate pipeline
        raise NotImplementedError("Calibration not yet implemented in orchestrator")

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Return capture stats for both cameras.

        Returns:
            Dict mapping camera_id to stats dict
        """
        with self._lock:
            if self._capture_service is None:
                return {}

            return self._capture_service.get_stats()

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
                from app.pipeline_service import SessionSummary
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

    def get_session_dir(self) -> Optional[Path]:
        """Return the current session directory if available.

        Returns:
            Path to current session directory, or None if not recording
        """
        with self._lock:
            if self._recording_service is None:
                return None

            return self._recording_service.get_session_dir()

    # Internal Event Handlers

    def _on_observation_detected_internal(self, event: ObservationDetectedEvent) -> None:
        """Handle ObservationDetectedEvent from EventBus.

        Feeds observations to pitch state machine and updates strike result.

        Args:
            event: ObservationDetectedEvent with stereo observation

        Note: Called from publisher's thread (DetectionService)
        """
        try:
            # Store latest observation for strike result
            self._latest_observation = event.observation

            # Feed to pitch tracker
            if self._pitch_tracker is not None:
                self._pitch_tracker.add_observation(event.observation)

                # Update state machine with detection counts
                # (In full implementation, would track lane/plate counts)
                self._pitch_tracker.update(
                    frame_ns=event.timestamp_ns,
                    lane_count=1,  # Simplified: assume observation is in lane
                    plate_count=0,
                    obs_count=1,
                )

        except Exception as e:
            logger.error(f"Error handling observation: {e}", exc_info=True)

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
                pitch_id=f"pitch_{pitch_data.pitch_index:05d}",
                observations=pitch_data.observations,
                timestamp_ns=pitch_data.end_ns,
                duration_ns=pitch_data.duration_ns(),
            )
            self._event_bus.publish(event)

            logger.info(f"Pitch ended: {pitch_data.pitch_index}, {len(pitch_data.observations)} observations")

        except Exception as e:
            logger.error(f"Error handling pitch end: {e}", exc_info=True)

    # EventBus Subscription Management

    def _subscribe_to_observations(self) -> None:
        """Subscribe to ObservationDetectedEvent from EventBus."""
        self._event_bus.subscribe(ObservationDetectedEvent, self._on_observation_detected_internal)
        logger.info("PipelineOrchestrator subscribed to ObservationDetectedEvent")

    def _unsubscribe_from_observations(self) -> None:
        """Unsubscribe from ObservationDetectedEvent."""
        self._event_bus.unsubscribe(ObservationDetectedEvent, self._on_observation_detected_internal)
        logger.info("PipelineOrchestrator unsubscribed from ObservationDetectedEvent")
