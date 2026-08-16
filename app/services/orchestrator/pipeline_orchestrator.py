"""PipelineOrchestrator - Coordinates all services via EventBus."""
from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Type

from app.contracts import CalibrationProfile, SessionSummary
from app.events.event_bus import EventBus
from app.pipeline.pitch_tracking_v2 import PitchConfig, PitchStateMachineV2
from app.pipeline.service_contracts import PipelineService
from app.services.analysis import AnalysisServiceImpl
from app.services.capture import CaptureServiceImpl
from app.services.detection import DetectionServiceImpl
from app.services.orchestrator.event_coordination import EventCoordinator, make_pitch_id
from app.services.orchestrator.lifecycle import shutdown_pipeline
from app.services.orchestrator.quality_diagnostics import (
    build_quality_diagnostics,
)
from app.services.orchestrator.service_startup import (
    load_and_validate_rig,
    ensure_services,
)
from app.services.orchestrator.roi_config import apply_runtime_rois
from app.services.recording import RecordingServiceImpl
from app.services.rig_profile import RigProfile, RigProfileService
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
    """Event-driven orchestrator coordinating services through EventBus."""

    def __init__(self, backend: str = "uvc"):
        self._backend = backend
        self._lock = threading.Lock()
        self._event_bus = EventBus()
        self._event_coordinator = EventCoordinator(self._event_bus)
        self._capture_service: Optional[CaptureServiceImpl] = None
        self._detection_service: Optional[DetectionServiceImpl] = None
        self._recording_service: Optional[RecordingServiceImpl] = None
        self._analysis_service: Optional[AnalysisServiceImpl] = None
        self._pitch_config = PitchConfig()
        self._pitch_tracker: Optional[PitchStateMachineV2] = None
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
        self._capturing = False
        self._detection_started = False
        self._recording_active = False
        self._recording_paused = False

    def start_capture(
        self,
        config: AppConfig,
        left_serial: str,
        right_serial: str,
        config_path: Optional[Path] = None,
    ) -> None:
        """Start capture on both cameras."""
        with self._lock:
            if self._capturing:
                raise RuntimeError("Capture already started")

            self._left_serial = left_serial
            self._right_serial = right_serial
            self._rig_profile_service = RigProfileService(
                config_path=Path(config_path) if config_path else Path("configs/default.yaml")
            )

            rig_result = load_and_validate_rig(
                self._rig_profile_service, config, self._backend,
                left_serial, right_serial,
            )
            self._active_rig_profile = rig_result.profile
            self._runtime_calibration_path = rig_result.calibration_path
            self._runtime_roi_path = rig_result.roi_path
            self._runtime_calibration_report = rig_result.calibration_report
            config = rig_result.config
            self._config = config
            self._config_path = config_path

            (
                self._capture_service,
                self._detection_service,
                self._recording_service,
                self._analysis_service,
            ) = ensure_services(
                self._event_bus, config, self._backend, rig_result,
                left_serial, right_serial,
                self._capture_service, self._detection_service,
                self._recording_service, self._analysis_service,
                self._record_dir, self._manual_speed_mph,
            )

            # Pitch tracker
            self._pitch_config = PitchConfig(
                min_active_frames=config.recording.session_min_active_frames,
                end_gap_frames=config.recording.session_end_gap_frames,
                pre_roll_ms=float(config.recording.pre_roll_ms),
                frame_rate=float(config.camera.fps),
            )
            self._pitch_tracker = PitchStateMachineV2(self._pitch_config)
            self._pitch_tracker.set_callbacks(
                on_pitch_start=self._event_coordinator.on_pitch_start,
                on_pitch_end=self._event_coordinator.on_pitch_end,
            )

            # Sync coordinator and subscribe
            self._event_coordinator.set_pitch_tracker(self._pitch_tracker)
            self._event_coordinator.set_rig_profile(self._active_rig_profile)
            self._event_coordinator.set_config(config)
            self._event_coordinator.subscribe()

            self._capture_service.start_capture(config, left_serial, right_serial)
            self._capturing = True
            logger.info("Capture started")

    def stop_capture(self) -> None:
        """Stop capture on both cameras. Idempotent and thread-safe."""
        with self._lock:
            if not self._capturing:
                return

            if self._capture_service is not None:
                self._capture_service.stop_capture()

            if self._detection_started and self._detection_service is not None:
                self._detection_service.stop_detection()
                self._detection_started = False

            self._event_coordinator.unsubscribe()

            self._capturing = False

    def shutdown(self) -> None:
        """Stop all active work before the UI object is destroyed."""
        shutdown_pipeline(self)

    def is_capturing(self) -> bool:
        """Check if capture is currently active."""
        with self._lock:
            return self._capturing

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Return the latest (left, right) frames for UI preview."""
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
        """Begin recording. Returns warning if disk space low, else empty string."""
        with self._lock:
            if not self._capturing:
                raise RuntimeError("Cannot start recording without capture")
            if self._recording_active:
                raise RuntimeError("Recording already active")
            if self._recording_service is None:
                raise RuntimeError("Recording service not initialized")

            session_id = session_name or "session"
            detection_started_here = analysis_started_here = False
            try:
                self._propagate_session_id(session_id)
                if not self._detection_started and self._detection_service is not None:
                    self._detection_service.configure_detectors(
                        config=self._config.detector,
                        mode=Mode.MODE_A,
                        detector_type="classical",
                    )
                    self._detection_service.configure_threading(mode="per_camera", worker_count=2)
                    detection_started_here = True
                    self._detection_service.start_detection()
                    self._detection_started = True

                if self._analysis_service is not None:
                    analysis_started_here = True
                    self._analysis_service.start_analysis(session_id=session_id)

                warning = self._recording_service.start_session(
                    session_name=session_id,
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
                        logger.exception("Roll back analysis failed")
                if detection_started_here and self._detection_service is not None:
                    try:
                        self._detection_service.stop_detection()
                        self._detection_started = False
                    except Exception:
                        logger.exception("Roll back detection failed")
                self._propagate_session_id(None)
                raise
            self._recording_active = True
            self._recording_paused = False
            return warning

    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for recordings."""
        with self._lock:
            self._record_dir = path
            if self._recording_service is not None:
                self._recording_service.set_record_directory(path)

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        """Set manual speed from external device (or None to clear)."""
        with self._lock:
            self._manual_speed_mph = speed_mph
            if self._analysis_service is not None:
                self._analysis_service.set_manual_speed_mph(speed_mph)
            if self._recording_service is not None:
                self._recording_service.set_manual_speed_mph(speed_mph)

    def stop_recording(self) -> RecordingBundle:
        """Stop recording and return the bundle."""
        with self._lock:
            if self._recording_service is None:
                raise RuntimeError("Recording service not initialized")

            if self._analysis_service is not None:
                self._analysis_service.stop_analysis()

            bundle = self._recording_service.stop_session()
            self._recording_active = False
            self._recording_paused = False
            self._propagate_session_id(None)
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

    def is_recording_paused(self) -> bool:
        """Check if the current recording session is paused."""
        with self._lock:
            return self._recording_paused

    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        """Reject runtime calibration — owned by Setup Doctor/tooling."""
        raise NotImplementedError(
            "Calibration is not run by PipelineOrchestrator. Use Setup Doctor "
            "or SubprocessToolingService for runtime capture profile setup."
        )

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Return capture stats for both cameras."""
        with self._lock:
            if self._capture_service is None:
                return {}
            return self._capture_service.get_stats()

    def get_quality_diagnostics(self) -> dict:
        """Return detailed runtime evidence."""
        with self._lock:
            capture = self._capture_service.get_stats() if self._capture_service else {}
            det_svc = self._detection_service
            rec_svc = self._recording_service
            ana_svc = self._analysis_service
            profile = self._active_rig_profile
            cal_report = dict(self._runtime_calibration_report or {})
        return build_quality_diagnostics(
            capture_stats=capture,
            detection_diagnostics=det_svc.get_quality_diagnostics() if det_svc else {},
            recording_stats=dict(rec_svc.get_frame_writer_stats()) if rec_svc else {},
            analysis_stats=dict(ana_svc.get_worker_stats()) if ana_svc else {},
            profile=profile,
            calibration_report=cal_report,
        )

    def get_plate_metrics(self) -> PlateMetricsStub:
        """Return latest plate-gated metrics (stubbed if unavailable)."""
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
        """Update detector configuration for the active session."""
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
        """Set detection threading mode."""
        with self._lock:
            if self._detection_service is None:
                return
            self._detection_service.configure_threading(mode, worker_count)

    def get_latest_detections(self) -> Dict[str, List[Detection]]:
        """Return latest raw detections by camera id."""
        with self._lock:
            if self._detection_service is None:
                return {}
            return self._detection_service.get_latest_detections()

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, List[Detection]]]:
        """Return latest gated detections by camera id and gate name."""
        with self._lock:
            if self._detection_service is None:
                return {}
            return self._detection_service.get_latest_gated_detections()

    def get_strike_result(self) -> StrikeResult:
        """Return latest strike determination."""
        with self._lock:
            obs = self._event_coordinator.latest_observation
            if self._analysis_service is None or obs is None:
                return StrikeResult(is_strike=False, sample_count=0, zone_row=None, zone_col=None)
            return self._analysis_service.calculate_strike_result(obs, self._config)

    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type for strike detection ('baseball' or 'softball')."""
        with self._lock:
            if self._analysis_service is not None:
                self._analysis_service.set_ball_type(ball_type)

    def set_batter_height_in(self, height_in: float) -> None:
        """Set batter height in inches for strike zone calculation."""
        with self._lock:
            if self._analysis_service is not None:
                self._analysis_service.set_batter_height_in(height_in)

    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        """Set strike zone top/bottom ratios for the active session."""
        with self._lock:
            if self._analysis_service is not None:
                self._analysis_service.set_strike_zone_ratios(top_ratio, bottom_ratio)

    def get_session_summary(self) -> SessionSummary:
        """Return the latest session summary."""
        with self._lock:
            if self._analysis_service is None:
                return SessionSummary(
                    session_id="none", pitch_count=0, strikes=0, balls=0,
                    heatmap=[[0] * 3 for _ in range(3)], pitches=[],
                )
            return self._analysis_service.get_session_summary()

    def get_recent_pitch_paths(self) -> List[List[StereoObservation]]:
        """Return recent pitch observation paths."""
        with self._lock:
            if self._analysis_service is None:
                return []
            return self._analysis_service.get_recent_pitch_paths()

    def get_recent_pitches(self, count: int = 10) -> List:
        """Return the most recent analyzed pitches for coaching UI compatibility."""
        return list(self.get_session_summary().pitches[-count:])

    def _propagate_session_id(self, session_id: Optional[str]) -> None:
        """Set or clear session_id on all event-producing services."""
        self._event_coordinator.set_session_id(session_id)
        if self._capture_service is not None:
            self._capture_service.set_session_id(session_id)
        if self._detection_service is not None:
            self._detection_service.set_session_id(session_id)

    def get_session_dir(self) -> Optional[Path]:
        """Return the current session directory, or None if not recording."""
        with self._lock:
            return self._recording_service.get_session_dir() if self._recording_service else None

    def get_last_session_summary(self) -> SessionSummary:
        """Compatibility wrapper for legacy UI API."""
        return self.get_session_summary()

    def reload_config(self, config: AppConfig) -> None:
        """Reload configuration for future analysis and recording operations."""
        with self._lock:
            self._config = config
            self._event_coordinator.set_config(config)
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
                    self._config, backend=self._backend,
                    left_serial=left_serial, right_serial=right_serial,
                )
                self._runtime_roi_path = self._rig_profile_service.roi_path(self._active_rig_profile)
            apply_runtime_rois(
                self._detection_service, self._runtime_roi_path,
                left_serial, right_serial,
            )

    def update_mound_distance(self, distance_ft: float) -> None:
        """Update mound distance in the active configuration."""
        with self._lock:
            if self._config is None:
                return
            self._config = replace(
                self._config, metrics=replace(self._config.metrics, release_plane_z_ft=distance_ft))
            if self._analysis_service is not None:
                self._analysis_service.update_config(self._config)

    def subscribe_event(self, event_type: Type, handler: Callable) -> None:
        """Register a public EventBus subscription."""
        self._event_bus.subscribe(event_type, handler)

    def unsubscribe_event(self, event_type: Type, handler: Callable) -> bool:
        """Remove a public EventBus subscription."""
        return self._event_bus.unsubscribe(event_type, handler)

    @staticmethod
    def _make_pitch_id(pitch_index: int) -> str:
        return make_pitch_id(pitch_index)

    def _to_field_coordinates(self, obs: StereoObservation) -> StereoObservation:
        self._event_coordinator.set_rig_profile(self._active_rig_profile)
        return self._event_coordinator._to_field_coordinates(obs)
