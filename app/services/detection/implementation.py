"""Stable facade for the event-driven detection service."""

from __future__ import annotations

from collections import Counter, deque
from pathlib import Path
import threading
import time
from typing import Dict, List, Optional, Tuple

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    FrameProcessingOpportunityEvent,
    FrameProcessingOutcomeEvent,
    StereoAssociationOutcomeEvent,
)
from app.monitoring.rig_drift import RigDriftMonitor
from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.pipeline.initialization import PipelineInitializer
from app.services.detection.configuration import DetectionConfiguration
from app.services.detection.diagnostics import detection_stats, quality_diagnostics
from app.services.detection.frame_processing import DetectionFrameHandler
from app.services.detection.interface import DetectionService, ObservationCallback
from app.services.detection.publication import DetectionEventPublisher
from configs.settings import AppConfig
from contracts import Detection, Frame, RayObservation, StereoObservation
from contracts.evidence import DecisionArtifactBindings, PairingOutcomeEvidence
from detect.config import DetectorConfig, Mode
from log_config.logger import get_logger
from trajectory.tracklets import TrackletBuilder

logger = get_logger(__name__)


class DetectionServiceImpl(DetectionService):
    """Coordinate detection collaborators behind the established public API."""

    def __init__(self, event_bus: EventBus, config: AppConfig):
        self._event_bus = event_bus
        self._config = config
        self._lock = threading.Lock()
        self._tracklet_lock = threading.Lock()
        self._initializer = PipelineInitializer()
        self._thread_pool: Optional[DetectionThreadPool] = None
        self._processor: Optional[DetectionProcessor] = None
        self._left_detector = None
        self._right_detector = None
        self._running = False
        self._subscribed = False
        self._observation_callbacks: List[ObservationCallback] = []
        self._lane_rois: Optional[Dict[str, List[Tuple[float, float]]]] = None
        self._plate_rois: Optional[Dict[str, List[Tuple[float, float]]]] = None
        self._calibration_path: Optional[Path] = None
        self._latest_observations: deque[StereoObservation] = deque(maxlen=64)
        self._detection_count = 0
        self._observation_count = 0
        self._pair_count = 0
        self._pair_rejection_counts: Counter[str] = Counter()
        self._pairing_frame_count = 0
        self._pairing_unmatched_counts: Counter[str] = Counter()
        self._detection_start_time = 0.0
        self._tracklet_builder = self._new_tracklet_builder(config)
        self._tracklet_updates = 0
        self._tracklet_starts = 0
        self._sync_drift_monitor = self._new_drift_monitor(config)
        self._last_drift_status = None
        self._decision_bindings_cache: Optional[DecisionArtifactBindings] = None
        self._session_id: Optional[str] = None
        self._configuration = DetectionConfiguration(self)
        self._frame_handler = DetectionFrameHandler(self)
        self._publisher = DetectionEventPublisher(self)
        logger.info("DetectionService initialized")

    def configure_detectors(
        self,
        config: DetectorConfig,
        mode: Mode,
        detector_type: str = "classical",
        model_path: Optional[str] = None,
        model_input_size: Tuple[int, int] = (640, 640),
        model_conf_threshold: float = 0.25,
        model_class_id: int = 0,
        model_format: str = "yolo_v5",
    ) -> None:
        """Configure and build the left and right detectors."""
        self._configuration.configure_detectors(
            config,
            mode,
            detector_type,
            model_path,
            model_input_size,
            model_conf_threshold,
            model_class_id,
            model_format,
        )

    def configure_threading(self, mode: str, worker_count: int) -> None:
        """Configure asynchronous detection workers."""
        self._configuration.configure_threading(mode, worker_count)

    def start_detection(self) -> None:
        """Build processing infrastructure and begin consuming frame events."""
        with self._lock:
            if self._running:
                return
            if self._left_detector is None or self._right_detector is None:
                raise RuntimeError("Detectors not configured. Call configure_detectors() first.")
            if self._thread_pool is None:
                raise RuntimeError("Threading not configured. Call configure_threading() first.")
            stereo_matcher = self._initializer.create_stereo_matcher(
                self._config,
                self._calibration_path or Path("calibration/stereo_calibration.npz"),
            )
            lane_gate, plate_gate, stereo_gate, plate_stereo_gate = self._configuration.build_gates()
            self._processor = DetectionProcessor(
                config=self._config,
                stereo_matcher=stereo_matcher,
                lane_gate=lane_gate,
                plate_gate=plate_gate,
                stereo_gate=stereo_gate,
                plate_stereo_gate=plate_stereo_gate,
                get_ball_radius_fn=lambda: 1.45,
            )
            self._wire_callbacks()
            self._reset_runtime_state()
            self._thread_pool.start(queue_size=6)
            self._subscribe_to_events()
            self._running = True
            self._detection_start_time = time.time()
            logger.info("Detection started")

    def stop_detection(self) -> None:
        """Stop workers, unsubscribe, and flush pending stereo pairs."""
        processor_to_flush = None
        with self._lock:
            if not self._running:
                return
            self._unsubscribe_from_events()
            if self._thread_pool is not None:
                self._thread_pool.stop()
            processor_to_flush = self._processor
            self._running = False
            logger.info("Detection stopped")
        if processor_to_flush is not None:
            processor_to_flush.flush_pairing_buffers()

    def process_frame(self, camera_id: str, frame: Frame) -> List[Detection]:
        """Enqueue a frame for asynchronous detection."""
        with self._lock:
            if not self._running:
                return []
            if self._thread_pool is not None:
                self._thread_pool.enqueue_frame(camera_id, frame)
        return []

    def get_latest_detections(self) -> Dict[str, List[Detection]]:
        """Return a snapshot of the latest raw detections."""
        with self._lock:
            if self._processor is None:
                return {}
            return self._processor.get_latest_detections()

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, List[Detection]]]:
        """Return a snapshot of lane- and plate-gated detections."""
        with self._lock:
            if self._processor is None:
                return {}
            return self._processor.get_latest_gated_detections()

    def get_latest_observations(self) -> List[StereoObservation]:
        """Return the bounded recent stereo observation snapshot."""
        with self._lock:
            return list(self._latest_observations)

    def on_observation_detected(self, callback: ObservationCallback) -> None:
        """Register a backward-compatible stereo observation callback."""
        with self._lock:
            self._observation_callbacks.append(callback)
            logger.debug(f"Registered observation callback ({len(self._observation_callbacks)} total)")

    def get_detection_stats(self) -> Dict[str, Optional[float]]:
        """Return detection and stereo utilization rates."""
        return detection_stats(self)

    def get_quality_diagnostics(self) -> dict:
        """Return detection, synchronization, and loss evidence."""
        return quality_diagnostics(self)

    def set_lane_rois(
        self,
        lane_rois: Dict[str, List[Tuple[float, float]]],
        plate_rois: Optional[Dict[str, List[Tuple[float, float]]]] = None,
    ) -> None:
        """Set lane and optional plate ROI polygons."""
        with self._lock:
            self._lane_rois = lane_rois
            self._plate_rois = plate_rois
            self._decision_bindings_cache = None
            gates = self._configuration.build_gates()
            if self._processor is not None:
                self._processor.update_gates(
                    lane_gate=gates[0],
                    plate_gate=gates[1],
                    stereo_gate=gates[2],
                    plate_stereo_gate=gates[3],
                )
            logger.info(f"Lane ROIs set for cameras: {list(lane_rois.keys())}")

    def set_runtime_calibration_path(self, calibration_path: Optional[Path]) -> None:
        """Set the calibration file used on the next detection start."""
        with self._lock:
            self._calibration_path = Path(calibration_path) if calibration_path is not None else None
            self._decision_bindings_cache = None
            logger.info(f"Runtime calibration path set to {self._calibration_path}")

    def is_running(self) -> bool:
        """Return whether detection workers are active."""
        with self._lock:
            return self._running

    def set_session_id(self, session_id: Optional[str]) -> None:
        """Set event metadata session identity."""
        with self._lock:
            self._session_id = session_id

    def update_config(self, config: AppConfig) -> None:
        """Update configuration for current and future processor work."""
        with self._lock:
            self._config = config
            self._decision_bindings_cache = None
            if self._processor is not None:
                self._processor.update_config(config)
        with self._tracklet_lock:
            self._tracklet_builder = self._new_tracklet_builder(config)
            self._tracklet_updates = 0
            self._tracklet_starts = 0
        self._sync_drift_monitor = self._new_drift_monitor(config)
        self._last_drift_status = None

    def _wire_callbacks(self) -> None:
        self._thread_pool.set_detect_callback(self._detect_frame)
        self._thread_pool.set_stereo_callback(self._on_stereo_result)
        self._thread_pool.set_frame_decision_callbacks(
            self._publish_frame_opportunity,
            self._publish_frame_outcome,
        )
        self._processor.set_stereo_pair_callback(self._on_stereo_pair)
        self._processor.set_ray_observation_callback(self._on_ray_observations)
        self._processor.set_pairing_outcome_callback(self._on_pairing_outcome)
        self._processor.set_association_outcome_callback(self._on_association_outcome)

    def _reset_runtime_state(self) -> None:
        self._latest_observations.clear()
        self._decision_bindings_cache = None
        self._detection_count = 0
        self._observation_count = 0
        self._pair_count = 0
        self._pair_rejection_counts.clear()
        self._pairing_frame_count = 0
        self._pairing_unmatched_counts.clear()
        self._tracklet_builder = self._new_tracklet_builder(self._config)
        self._tracklet_updates = 0
        self._tracklet_starts = 0

    def _on_frame_captured_internal(self, event: FrameCapturedEvent) -> None:
        self._frame_handler.on_frame_captured(event)

    def _detect_frame(self, camera_id: str, frame: Frame) -> List[Detection]:
        return self._frame_handler.detect_frame(camera_id, frame)

    def _on_stereo_result(self, camera_id: str, frame: Frame, detections: List[Detection]) -> None:
        self._frame_handler.on_stereo_result(camera_id, frame, detections)

    def _publish_frame_opportunity(self, event: FrameProcessingOpportunityEvent) -> None:
        self._publisher.publish_frame_opportunity(event)

    def _publish_frame_outcome(self, event: FrameProcessingOutcomeEvent) -> None:
        self._publisher.publish_frame_outcome(event)

    def _on_pairing_outcome(self, outcome: PairingOutcomeEvidence) -> None:
        self._publisher.on_pairing_outcome(outcome)

    def _on_association_outcome(self, event: StereoAssociationOutcomeEvent) -> None:
        self._publisher.on_association_outcome(event)

    def _decision_bindings(self, algorithm_name: str, algorithm_version: str) -> DecisionArtifactBindings:
        return self._configuration.decision_bindings(algorithm_name, algorithm_version)

    def _on_stereo_pair(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: List[Detection],
        right_detections: List[Detection],
        observations: List[StereoObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        self._publisher.on_stereo_pair(
            left_frame,
            right_frame,
            left_detections,
            right_detections,
            observations,
            lane_count,
            plate_count,
        )

    def _on_ray_observations(
        self,
        camera_id: str,
        frame: Frame,
        observations: List[RayObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        self._publisher.on_ray_observations(camera_id, frame, observations, lane_count, plate_count)

    def _subscribe_to_events(self) -> None:
        if self._subscribed:
            return
        self._event_bus.subscribe(FrameCapturedEvent, self._on_frame_captured_internal)
        self._subscribed = True
        logger.info("DetectionService subscribed to EventBus")

    def _unsubscribe_from_events(self) -> None:
        if not self._subscribed:
            return
        self._event_bus.unsubscribe(FrameCapturedEvent, self._on_frame_captured_internal)
        self._subscribed = False
        logger.info("DetectionService unsubscribed from EventBus")

    @staticmethod
    def _new_tracklet_builder(config: AppConfig) -> TrackletBuilder:
        return TrackletBuilder(
            max_speed_px_s=config.detector.filters.max_velocity or 5000.0,
            max_gap_frames=2,
        )

    @staticmethod
    def _new_drift_monitor(config: AppConfig) -> RigDriftMonitor:
        tolerance = float(config.stereo.pairing_tolerance_ms)
        return RigDriftMonitor(
            "pair_skew_ms",
            warn_threshold=tolerance * 0.5,
            fail_threshold=tolerance,
            recovery_threshold=tolerance * 0.25,
            window_size=30,
            required_bad_windows=3,
        )
