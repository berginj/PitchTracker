"""DetectionService implementation with EventBus integration.

Manages detection pipeline:
- Object detection in frames
- Stereo matching between camera pairs
- Lane gating and filtering
- Observation generation and publishing to EventBus
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import threading
from typing import Dict, List, Optional, Tuple

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    FrameProcessingOpportunityEvent,
    FrameProcessingOutcomeEvent,
    ObservationDetectedEvent,
    PairingOutcomeEvent,
    RayObservationDetectedEvent,
    StereoAssociationOutcomeEvent,
    StereoFrameProcessedEvent,
)
from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.detection.decision_ids import canonicalize_detection_ids, stereo_pair_id
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.pipeline.initialization import PipelineInitializer
from app.services.detection.interface import DetectionService, ObservationCallback
from configs.settings import AppConfig
from contracts import Detection, Frame, RayObservation, StereoObservation
from contracts.evidence import DecisionArtifactBindings, PairingOutcomeEvidence
from detect.config import DetectorConfig, Mode
from detect.lane import LaneGate, LaneRoi
from log_config.logger import get_logger
from stereo import StereoLaneGate
from stereo.association import pair_timing
from trajectory.tracklets import TrackletBuilder
from app.monitoring.rig_drift import RigDriftMonitor

logger = get_logger(__name__)


class DetectionServiceImpl(DetectionService):
    """Event-driven detection service implementation.

    Features:
    - EventBus integration for event-driven detection
    - Subscribes to FrameCapturedEvent (best-effort, can lag)
    - Publishes ObservationDetectedEvent when observations generated
    - Wraps DetectionThreadPool for threading
    - Wraps DetectionProcessor for stereo matching
    - Thread-safe detection and stats

    Architecture:
        - Subscribes to FrameCapturedEvent from EventBus
        - Enqueues frames to DetectionThreadPool
        - DetectionThreadPool runs detection in worker threads
        - Results passed to DetectionProcessor for stereo matching
        - DetectionProcessor generates StereoObservations
        - Publishes ObservationDetectedEvent to EventBus

    Thread Safety:
        - All public methods are thread-safe
        - Detection runs in separate threads (non-blocking)
        - EventBus handlers run on publisher's thread
    """

    def __init__(self, event_bus: EventBus, config: AppConfig):
        """Initialize detection service.

        Args:
            event_bus: EventBus instance for subscribing/publishing events
            config: Application configuration
        """
        self._event_bus = event_bus
        self._config = config
        self._lock = threading.Lock()
        self._tracklet_lock = threading.Lock()

        # Initialize detection infrastructure
        self._initializer = PipelineInitializer()
        self._thread_pool: Optional[DetectionThreadPool] = None
        self._processor: Optional[DetectionProcessor] = None

        # Detectors (left/right)
        self._left_detector = None
        self._right_detector = None

        # State
        self._running = False
        self._subscribed = False

        # Callbacks (for backward compatibility)
        self._observation_callbacks: List[ObservationCallback] = []

        # Lane ROIs (optional)
        self._lane_rois: Optional[Dict[str, List[Tuple[float, float]]]] = None
        self._plate_rois: Optional[Dict[str, List[Tuple[float, float]]]] = None
        self._calibration_path: Optional[Path] = None
        self._latest_observations: deque[StereoObservation] = deque(maxlen=64)

        # Stats tracking
        self._detection_count = 0
        self._observation_count = 0
        self._pair_count = 0
        self._pair_rejection_counts: Counter[str] = Counter()
        self._pairing_frame_count = 0
        self._pairing_unmatched_counts: Counter[str] = Counter()
        self._detection_start_time = 0.0
        self._tracklet_builder = TrackletBuilder(
            max_speed_px_s=config.detector.filters.max_velocity or 5000.0,
            max_gap_frames=2,
        )
        self._tracklet_updates = 0
        self._tracklet_starts = 0
        tolerance = float(config.stereo.pairing_tolerance_ms)
        self._sync_drift_monitor = RigDriftMonitor(
            "pair_skew_ms",
            warn_threshold=tolerance * 0.5,
            fail_threshold=tolerance,
            recovery_threshold=tolerance * 0.25,
            window_size=30,
            required_bad_windows=3,
        )
        self._last_drift_status = None
        self._decision_bindings_cache: Optional[DecisionArtifactBindings] = None

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
        """Configure detection parameters.

        Args:
            config: CV detector configuration (blur, threshold, etc.)
            mode: Detection mode (MODE_A or MODE_B)
            detector_type: "classical" or "ml"
            model_path: Path to ML model (if detector_type="ml")
            model_input_size: Model input dimensions
            model_conf_threshold: Confidence threshold for ML detections
            model_class_id: Class ID to detect
            model_format: Model format ("yolo_v5", "yolo_v8", etc.)

        Raises:
            ModelLoadError: If ML model cannot be loaded
            ValueError: If configuration is invalid
        """
        with self._lock:
            # Configure PipelineInitializer internal state
            self._initializer._detector_config = config
            self._initializer._detector_mode = mode
            self._initializer._detector_type = detector_type
            self._initializer._detector_model_path = model_path
            self._initializer._detector_model_input_size = model_input_size
            self._initializer._detector_model_conf_threshold = model_conf_threshold
            self._initializer._detector_model_class_id = model_class_id
            self._initializer._detector_model_format = model_format

            # Build detectors (returns dict with "left" and "right" keys)
            detectors = self._initializer.build_detectors(left_id="left", right_id="right", lane_polygon=None)
            self._left_detector = detectors["left"]
            self._right_detector = detectors["right"]
            self._decision_bindings_cache = None

            logger.info(f"Detectors configured: type={detector_type}, mode={mode}")

    def configure_threading(self, mode: str, worker_count: int) -> None:
        """Configure detection threading mode.

        Args:
            mode: "per_camera" (one thread per camera) or
                  "worker_pool" (shared thread pool)
            worker_count: Number of worker threads (for worker_pool mode)

        Raises:
            ValueError: If mode is invalid or worker_count <= 0
        """
        with self._lock:
            if mode not in ("per_camera", "worker_pool"):
                raise ValueError(f"Invalid threading mode: {mode}")
            if worker_count <= 0:
                raise ValueError(f"Invalid worker_count: {worker_count}")

            # Create thread pool if not exists
            if self._thread_pool is None:
                self._thread_pool = DetectionThreadPool(mode, worker_count)
            else:
                # Update mode (requires restart to take effect)
                self._thread_pool.set_mode(mode, worker_count)

            logger.info(f"Threading configured: mode={mode}, workers={worker_count}")

    def start_detection(self) -> None:
        """Start detection processing.

        Must be called after configure_detectors() and configure_threading().

        Raises:
            RuntimeError: If detectors or threading not configured
        """
        with self._lock:
            if self._running:
                return

            if self._left_detector is None or self._right_detector is None:
                raise RuntimeError("Detectors not configured. Call configure_detectors() first.")

            if self._thread_pool is None:
                raise RuntimeError("Threading not configured. Call configure_threading() first.")

            # Build stereo matcher
            stereo_matcher = self._initializer.create_stereo_matcher(
                self._config,
                self._calibration_path or Path("calibration/stereo_calibration.npz"),
            )

            # Build processor
            lane_gate, plate_gate, stereo_gate, plate_stereo_gate = self._build_gates()
            self._processor = DetectionProcessor(
                config=self._config,
                stereo_matcher=stereo_matcher,
                lane_gate=lane_gate,
                plate_gate=plate_gate,
                stereo_gate=stereo_gate,
                plate_stereo_gate=plate_stereo_gate,
                get_ball_radius_fn=lambda: 1.45,  # Default ball radius
            )

            # Set callbacks on thread pool
            self._thread_pool.set_detect_callback(self._detect_frame)
            self._thread_pool.set_stereo_callback(self._on_stereo_result)
            self._thread_pool.set_frame_decision_callbacks(
                self._publish_frame_opportunity,
                self._publish_frame_outcome,
            )

            # Set callback on processor
            self._processor.set_stereo_pair_callback(self._on_stereo_pair)
            self._processor.set_ray_observation_callback(self._on_ray_observations)
            self._processor.set_pairing_outcome_callback(self._on_pairing_outcome)
            self._processor.set_association_outcome_callback(self._on_association_outcome)

            self._latest_observations.clear()
            self._decision_bindings_cache = None
            self._detection_count = 0
            self._observation_count = 0
            self._pair_count = 0
            self._pair_rejection_counts.clear()
            self._pairing_frame_count = 0
            self._pairing_unmatched_counts.clear()
            self._tracklet_builder = TrackletBuilder(
                max_speed_px_s=self._config.detector.filters.max_velocity or 5000.0,
                max_gap_frames=2,
            )
            self._tracklet_updates = 0
            self._tracklet_starts = 0

            # Start thread pool
            self._thread_pool.start(queue_size=6)

            # Subscribe to EventBus
            self._subscribe_to_events()

            self._running = True
            self._detection_start_time = __import__("time").time()

            logger.info("Detection started")

    def stop_detection(self) -> None:
        """Stop detection processing.

        Thread-Safe: Can be called from any thread.
        Idempotent: Safe to call multiple times.
        """
        processor_to_flush = None
        with self._lock:
            if not self._running:
                return

            # Unsubscribe from EventBus
            self._unsubscribe_from_events()

            # Stop thread pool
            if self._thread_pool is not None:
                self._thread_pool.stop()
            processor_to_flush = self._processor

            self._running = False

            logger.info("Detection stopped")
        if processor_to_flush is not None:
            processor_to_flush.flush_pairing_buffers()

    def process_frame(self, camera_id: str, frame: Frame) -> List[Detection]:
        """Process a frame and return detections.

        This is typically called from a frame callback, not directly.

        Args:
            camera_id: Camera identifier ("left" or "right")
            frame: Frame to process

        Returns:
            List of detections found in frame

        Thread-Safety: Can be called concurrently from multiple threads.
        Performance: Enqueues frame for async processing, returns immediately.
        """
        with self._lock:
            if not self._running:
                return []

            # Enqueue frame for detection
            if self._thread_pool is not None:
                self._thread_pool.enqueue_frame(camera_id, frame)

        # Return empty - actual detections come via callback
        return []

    def get_latest_detections(self) -> Dict[str, List[Detection]]:
        """Get latest raw detections by camera.

        Returns:
            Dict mapping camera_id to list of detections

        Thread-Safe: Returns snapshot of latest detections.
        """
        with self._lock:
            if self._processor is None:
                return {}
            return self._processor.get_latest_detections()

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, List[Detection]]]:
        """Get latest detections filtered by lane gates.

        Returns:
            Dict mapping camera_id to dict of gate_name to filtered detections

        Thread-Safe: Returns snapshot of latest gated detections.
        """
        with self._lock:
            if self._processor is None:
                return {}
            return self._processor.get_latest_gated_detections()

    def get_latest_observations(self) -> List[StereoObservation]:
        """Get latest stereo observations from matched detections.

        Returns:
            List of stereo observations with 3D positions

        Thread-Safe: Returns snapshot of latest observations.
        """
        # Observations are published via EventBus, not buffered here
        with self._lock:
            return list(self._latest_observations)

    def on_observation_detected(self, callback: ObservationCallback) -> None:
        """Register callback for stereo observation events.

        Callback will be invoked from detection thread when observation
        is generated from stereo matching.

        Args:
            callback: Function to call with observation

        Thread-Safety:
            - Callback registration is thread-safe
            - Callback invoked from detection thread
            - Callback should be fast (< 5ms) to avoid blocking detection
        """
        with self._lock:
            self._observation_callbacks.append(callback)
            logger.debug(f"Registered observation callback ({len(self._observation_callbacks)} total)")

    def get_detection_stats(self) -> Dict[str, Optional[float]]:
        """Get detection performance statistics.

        Returns:
            Dict with statistics:
            - detections_per_sec: Detection rate
            - observations_per_sec: Observation rate
            - avg_detection_ms: Average detection time
            - stereo_detection_utilization: Fraction of camera detections used
              by stereo observations (two detections per observation)

        Thread-Safe: Returns snapshot of current stats.
        """
        with self._lock:
            if not self._running or self._detection_start_time == 0:
                return {
                    "detections_per_sec": 0.0,
                    "observations_per_sec": 0.0,
                    "avg_detection_ms": 0.0,
                    "stereo_detection_utilization": None,
                }

            elapsed = __import__("time").time() - self._detection_start_time
            if elapsed == 0:
                elapsed = 0.001  # Avoid division by zero

            return {
                "detections_per_sec": self._detection_count / elapsed,
                "observations_per_sec": self._observation_count / elapsed,
                "avg_detection_ms": 0.0,  # Future: Track detection timing metrics
                "stereo_detection_utilization": (
                    min(1.0, (2.0 * self._observation_count) / self._detection_count)
                    if self._detection_count > 0
                    else None
                ),
            }

    def get_quality_diagnostics(self) -> dict:
        """Return detection rates plus pair-level synchronization evidence."""
        detection = self.get_detection_stats()
        with self._lock:
            processor = self._processor
            thread_pool = self._thread_pool
        sync = processor.get_sync_stats() if processor is not None else {}
        processing = thread_pool.get_runtime_stats() if thread_pool is not None else _empty_pool_stats()
        input_opportunities = sum(processing[name]["queue_attempts"] for name in ("left", "right"))
        lost_attempts = (
            sum(processing[name]["queue_drops"] + processing[name]["failures"] for name in ("left", "right"))
            + processing["results"]["queue_drops"]
            + processing["results"]["failures"]
        )
        detection_loss = {
            "numerator": lost_attempts,
            "denominator": input_opportunities,
            "value": (min(1.0, lost_attempts / input_opportunities) if input_opportunities > 0 else None),
        }
        detection["detection_loss_rate"] = detection_loss["value"]
        with self._tracklet_lock:
            detection["tracklet_start_rate"] = (
                self._tracklet_starts / self._tracklet_updates if self._tracklet_updates > 0 else None
            )
        drift = self._last_drift_status
        with self._lock:
            pair_count = self._pair_count
            rejection_counts = dict(self._pair_rejection_counts)
            pairing_frame_count = self._pairing_frame_count
            pairing_unmatched_counts = dict(self._pairing_unmatched_counts)
        rejection_reasons = {
            "PAIR_SKEW_OUT_OF_TOLERANCE",
            "NO_CANDIDATES",
            "NO_VALID_STEREO_ASSOCIATION",
            *rejection_counts,
        }
        return {
            "detection": detection,
            "processing": processing,
            "detection_loss": detection_loss,
            "sync": sync,
            "drift": None if drift is None else drift.__dict__.copy(),
            "pair_outcomes": {
                "denominator": pair_count,
                "rejection_counts": rejection_counts,
                "rejection_rates": {
                    reason: (rejection_counts.get(reason, 0) / pair_count if pair_count > 0 else None)
                    for reason in sorted(rejection_reasons)
                },
            },
            "pairing_frame_outcomes": {
                "denominator": pairing_frame_count,
                "unmatched_counts": pairing_unmatched_counts,
                "unmatched_rates": {
                    reason: (
                        pairing_unmatched_counts.get(reason, 0) / pairing_frame_count
                        if pairing_frame_count > 0
                        else None
                    )
                    for reason in sorted(pairing_unmatched_counts)
                },
                "total_unmatched_rate": (
                    sum(pairing_unmatched_counts.values()) / pairing_frame_count
                    if pairing_frame_count > 0
                    else None
                ),
            },
        }

    def set_lane_rois(
        self,
        lane_rois: Dict[str, List[Tuple[float, float]]],
        plate_rois: Optional[Dict[str, List[Tuple[float, float]]]] = None,
    ) -> None:
        """Set ROI polygons for lane gating.

        Args:
            lane_rois: Dict mapping camera_id to polygon points (lane gate)
            plate_rois: Optional dict for plate gate polygons

        Raises:
            InvalidROIError: If ROI polygons are invalid
        """
        with self._lock:
            self._lane_rois = lane_rois
            self._plate_rois = plate_rois
            self._decision_bindings_cache = None

            lane_gate, plate_gate, stereo_gate, plate_stereo_gate = self._build_gates()
            if self._processor is not None:
                self._processor.update_gates(
                    lane_gate=lane_gate,
                    plate_gate=plate_gate,
                    stereo_gate=stereo_gate,
                    plate_stereo_gate=plate_stereo_gate,
                )
            logger.info(f"Lane ROIs set for cameras: {list(lane_rois.keys())}")

    def set_runtime_calibration_path(self, calibration_path: Optional[Path]) -> None:
        """Set the calibration file used when detection starts."""
        with self._lock:
            self._calibration_path = Path(calibration_path) if calibration_path is not None else None
            self._decision_bindings_cache = None
            logger.info(f"Runtime calibration path set to {self._calibration_path}")

    def is_running(self) -> bool:
        """Check if detection is currently running.

        Returns:
            True if detection threads are active, False otherwise
        """
        with self._lock:
            return self._running

    def update_config(self, config: AppConfig) -> None:
        """Update detection configuration used for future processor work."""
        with self._lock:
            self._config = config
            self._decision_bindings_cache = None
            if self._processor is not None:
                self._processor.update_config(config)
        with self._tracklet_lock:
            self._tracklet_builder = TrackletBuilder(
                max_speed_px_s=config.detector.filters.max_velocity or 5000.0,
                max_gap_frames=2,
            )
            self._tracklet_updates = 0
            self._tracklet_starts = 0
        tolerance = float(config.stereo.pairing_tolerance_ms)
        self._sync_drift_monitor = RigDriftMonitor(
            "pair_skew_ms",
            warn_threshold=tolerance * 0.5,
            fail_threshold=tolerance,
            recovery_threshold=tolerance * 0.25,
            window_size=30,
            required_bad_windows=3,
        )
        self._last_drift_status = None

    # Internal Event Handlers

    def _on_frame_captured_internal(self, event: FrameCapturedEvent) -> None:
        """Handle FrameCapturedEvent from EventBus.

        Enqueues frame for detection processing.

        Args:
            event: FrameCapturedEvent with camera_id, frame, timestamp_ns

        Note: Called from camera capture thread
        """
        try:
            # Process frame (enqueues for async detection)
            self.process_frame(event.camera_id, event.frame)

        except Exception as e:
            logger.error(f"Error handling frame capture: {e}", exc_info=True)

    def _detect_frame(self, camera_id: str, frame: Frame) -> List[Detection]:
        """Detect objects in frame.

        Called by DetectionThreadPool worker threads.

        Args:
            camera_id: Camera identifier ("left" or "right")
            frame: Frame to process

        Returns:
            List of detections
        """
        # Detector failures must reach DetectionThreadPool so they contribute to
        # typed failure accounting and are not emitted as empty stereo results.
        detector = self._left_detector if camera_id == "left" else self._right_detector
        if detector is None:
            raise RuntimeError(f"Detector is not configured for {camera_id} camera")

        detections = canonicalize_detection_ids(frame, detector.detect(frame))

        with self._lock:
            self._detection_count += len(detections)

        return detections

    def _on_stereo_result(self, camera_id: str, frame: Frame, detections: List[Detection]) -> None:
        """Handle detection result from thread pool.

        Passes result to processor for stereo matching.

        Args:
            camera_id: Camera identifier
            frame: Processed frame
            detections: Detection results
        """
        try:
            if self._processor is not None:
                with self._tracklet_lock:
                    previous_ids = {
                        track.tracklet_id for track in self._tracklet_builder.active(camera_id)
                    }
                    tracks, decisions = self._tracklet_builder.update_with_decisions(camera_id, detections)
                    current_ids = {track.tracklet_id for track in tracks}
                    self._tracklet_updates += len(detections)
                    self._tracklet_starts += len(current_ids - previous_ids)
                min_length = max(1, int(self._config.detector.min_consecutive))
                track_lengths = {track.tracklet_id: len(track.detections) for track in tracks}
                decision_by_candidate = {decision.candidate_id: decision for decision in decisions}
                enriched: list[Detection] = []
                for detection in detections:
                    decision = decision_by_candidate.get(detection.candidate_id)
                    tracklet_id = None if decision is None else decision.tracklet_id
                    eligible_for_association = bool(
                        tracklet_id is not None and track_lengths.get(tracklet_id, 0) >= min_length
                    )
                    reasons = () if eligible_for_association else ("TRACKLET_RAMP_UP",)
                    enriched.append(
                        replace(
                            detection,
                            tracklet_id=tracklet_id,
                            tracklet_action=None if decision is None else decision.action,
                            association_eligible=eligible_for_association,
                            rejection_reasons=reasons,
                        )
                    )
                # The result-list object is shared with DetectionThreadPool, so
                # its terminal event observes the same lineage sent downstream.
                detections[:] = enriched
                eligible = [detection for detection in enriched if detection.association_eligible]
                self._processor.process_detection_result(camera_id, frame, eligible)

        except Exception as e:
            logger.error(f"Error processing stereo result: {e}", exc_info=True)
            raise

    def _publish_frame_opportunity(self, event: FrameProcessingOpportunityEvent) -> None:
        self._event_bus.publish(
            replace(event, bindings=self._decision_bindings("detection_pipeline", "2"))
        )

    def _publish_frame_outcome(self, event: FrameProcessingOutcomeEvent) -> None:
        self._event_bus.publish(
            replace(event, bindings=self._decision_bindings("detection_pipeline", "2"))
        )

    def _on_pairing_outcome(self, outcome: PairingOutcomeEvidence) -> None:
        with self._lock:
            self._pairing_frame_count += outcome.frame_count
            if outcome.status == "UNMATCHED":
                reason = outcome.reason_codes[0] if outcome.reason_codes else "UNSPECIFIED"
                self._pairing_unmatched_counts[reason] += outcome.frame_count
        self._event_bus.publish(
            PairingOutcomeEvent(
                outcome,
                bindings=self._decision_bindings(f"{outcome.pairing_mode}_pairing", "2"),
            )
        )

    def _on_association_outcome(self, event: StereoAssociationOutcomeEvent) -> None:
        version = "2" if event.primary_algorithm == "global_v2" else "1"
        self._event_bus.publish(
            replace(
                event,
                bindings=self._decision_bindings(event.primary_algorithm, version),
            )
        )

    def _decision_bindings(self, algorithm_name: str, algorithm_version: str) -> DecisionArtifactBindings:
        base = self._decision_bindings_cache
        if base is None:
            config_payload = json.dumps(asdict(self._config), sort_keys=True, default=str).encode("utf-8")
            roi_payload = json.dumps(
                {"lane": self._lane_rois, "plate": self._plate_rois},
                sort_keys=True,
                default=str,
            ).encode("utf-8")
            detector = self._left_detector
            detector_name = None if detector is None else f"{detector.__class__.__module__}.{detector.__class__.__name__}"
            model_path_raw = getattr(self._initializer, "_detector_model_path", None)
            model_path = None if not model_path_raw else Path(str(model_path_raw))
            base = DecisionArtifactBindings(
                config_sha256=hashlib.sha256(config_payload).hexdigest(),
                calibration_sha256=_file_sha256(self._calibration_path),
                roi_sha256=hashlib.sha256(roi_payload).hexdigest(),
                detector_name=detector_name,
                detector_version=str(getattr(detector, "version", "unknown")) if detector is not None else None,
                model_sha256=_file_sha256(model_path),
            )
            self._decision_bindings_cache = base
        return replace(base, algorithm_name=algorithm_name, algorithm_version=algorithm_version)

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
        """Handle stereo pair processing result.

        Publishes ObservationDetectedEvent for each observation.

        Args:
            left_frame: Left camera frame
            right_frame: Right camera frame
            left_detections: Left camera detections
            right_detections: Right camera detections
            observations: Stereo observations generated
            lane_count: Number of lane-gated detections
            plate_count: Number of plate-gated detections
        """
        try:
            timing = pair_timing(
                left_frame.t_capture_monotonic_ns,
                right_frame.t_capture_monotonic_ns,
                int(getattr(self._config.stereo, "time_sync_offset_ns", 0)),
            )
            pair_timestamp_ns = timing.timestamp_ns
            pair_skew_ms = timing.adjusted_skew_ns / 1e6
            self._last_drift_status = self._sync_drift_monitor.update(pair_skew_ms)
            rejection_reasons: list[str] = []
            tolerance_ms = float(self._config.stereo.pairing_tolerance_ms)
            if pair_skew_ms > tolerance_ms:
                rejection_reasons.append("PAIR_SKEW_OUT_OF_TOLERANCE")
            elif not left_detections and not right_detections:
                rejection_reasons.append("NO_CANDIDATES")
            elif not observations:
                rejection_reasons.append("NO_VALID_STEREO_ASSOCIATION")
            with self._lock:
                self._pair_count += 1
                self._pair_rejection_counts.update(rejection_reasons)
            self._event_bus.publish(
                StereoFrameProcessedEvent(
                    pair_id=stereo_pair_id(left_frame, right_frame),
                    timestamp_ns=pair_timestamp_ns,
                    left_timestamp_ns=left_frame.t_capture_monotonic_ns,
                    right_timestamp_ns=right_frame.t_capture_monotonic_ns,
                    left_frame_index=left_frame.frame_index,
                    right_frame_index=right_frame.frame_index,
                    lane_count=lane_count,
                    plate_count=plate_count,
                    observations=tuple(observations),
                    rejection_reasons=tuple(rejection_reasons),
                    adjusted_left_timestamp_ns=timing.adjusted_left_ns,
                    adjusted_right_timestamp_ns=timing.adjusted_right_ns,
                    time_sync_offset_ns=timing.right_offset_ns,
                )
            )

            # Publish each observation to EventBus
            for obs in observations:
                with self._lock:
                    self._latest_observations.append(obs)
                event = ObservationDetectedEvent(observation=obs, timestamp_ns=obs.t_ns, confidence=obs.confidence)
                self._event_bus.publish(event)

                # Invoke registered callbacks (backward compatibility)
                for callback in self._observation_callbacks:
                    try:
                        callback(obs)
                    except Exception as e:
                        logger.error(f"Observation callback error: {e}", exc_info=True)

            # Track stats
            with self._lock:
                self._observation_count += len(observations)

        except Exception as e:
            logger.error(f"Error handling stereo pair: {e}", exc_info=True)

    def _on_ray_observations(
        self,
        camera_id: str,
        frame: Frame,
        observations: List[RayObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        """Publish per-camera ray observations generated by the processor."""
        del camera_id, frame, lane_count, plate_count
        try:
            for obs in observations:
                self._event_bus.publish(
                    RayObservationDetectedEvent(
                        observation=obs,
                        timestamp_ns=obs.t_ns,
                        confidence=obs.confidence,
                    )
                )
        except Exception as e:
            logger.error(f"Error handling ray observations: {e}", exc_info=True)

    # EventBus Subscription Management

    def _subscribe_to_events(self) -> None:
        """Subscribe to EventBus events.

        Called when detection starts.
        """
        if self._subscribed:
            return

        self._event_bus.subscribe(FrameCapturedEvent, self._on_frame_captured_internal)

        self._subscribed = True
        logger.info("DetectionService subscribed to EventBus")

    def _build_gates(
        self,
    ) -> tuple[Optional[LaneGate], Optional[LaneGate], Optional[StereoLaneGate], Optional[StereoLaneGate]]:
        lane_gate = self._build_lane_gate(self._lane_rois)
        plate_gate = self._build_lane_gate(self._plate_rois)
        stereo_gate = StereoLaneGate(lane_gate) if lane_gate is not None else None
        plate_stereo_gate = StereoLaneGate(plate_gate) if plate_gate is not None else None
        return lane_gate, plate_gate, stereo_gate, plate_stereo_gate

    @staticmethod
    def _build_lane_gate(roi_map: Optional[Dict[str, List[Tuple[float, float]]]]) -> Optional[LaneGate]:
        if not roi_map:
            return None

        return LaneGate(
            roi_by_camera={camera_id: LaneRoi(polygon=list(points)) for camera_id, points in roi_map.items()}
        )

    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from EventBus events.

        Called when detection stops.
        """
        if not self._subscribed:
            return

        self._event_bus.unsubscribe(FrameCapturedEvent, self._on_frame_captured_internal)

        self._subscribed = False
        logger.info("DetectionService unsubscribed from EventBus")


def _file_sha256(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_pool_stats() -> dict:
    """Return a zero-opportunity pool snapshot before threading is configured."""
    payload = {
        name: {
            "attempts": 0,
            "failures": 0,
            "queue_attempts": 0,
            "queue_drops": 0,
            "failure_rate": {"numerator": 0, "denominator": 0, "value": None},
            "queue_drop_rate": {"numerator": 0, "denominator": 0, "value": None},
        }
        for name in ("left", "right", "results")
    }
    payload["frame_conservation"] = {
        "offered": 0,
        "terminal": 0,
        "outstanding": 0,
        "balanced": True,
        "terminal_outcomes": {},
    }
    return payload
