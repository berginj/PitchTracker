"""DetectionService implementation with EventBus integration.

Manages detection pipeline:
- Object detection in frames
- Stereo matching between camera pairs
- Lane gating and filtering
- Observation generation and publishing to EventBus
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List, Optional, Tuple

from app.events.event_bus import EventBus
from app.events.event_types import FrameCapturedEvent, ObservationDetectedEvent
from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.pipeline.initialization import PipelineInitializer
from app.services.detection.interface import DetectionService, ObservationCallback
from configs.settings import AppConfig
from contracts import Detection, Frame, StereoObservation
from detect.config import DetectorConfig, Mode
from log_config.logger import get_logger

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

        # Stats tracking
        self._detection_count = 0
        self._observation_count = 0
        self._detection_start_time = 0.0

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
            detectors = self._initializer.build_detectors(
                left_id="left",
                right_id="right",
                lane_polygon=None
            )
            self._left_detector = detectors["left"]
            self._right_detector = detectors["right"]

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
            stereo_matcher = self._initializer.create_stereo_matcher(self._config)

            # Build processor
            self._processor = DetectionProcessor(
                config=self._config,
                stereo_matcher=stereo_matcher,
                lane_gate=None,  # Will be set via set_lane_rois()
                plate_gate=None,
                stereo_gate=None,
                plate_stereo_gate=None,
                get_ball_radius_fn=lambda: 1.45  # Default ball radius
            )

            # Set callbacks on thread pool
            self._thread_pool.set_detect_callback(self._detect_frame)
            self._thread_pool.set_stereo_callback(self._on_stereo_result)

            # Set callback on processor
            self._processor.set_stereo_pair_callback(self._on_stereo_pair)

            # Start thread pool
            self._thread_pool.start(queue_size=6)

            # Subscribe to EventBus
            self._subscribe_to_events()

            self._running = True
            self._detection_start_time = __import__('time').time()

            logger.info("Detection started")

    def stop_detection(self) -> None:
        """Stop detection processing.

        Thread-Safe: Can be called from any thread.
        Idempotent: Safe to call multiple times.
        """
        with self._lock:
            if not self._running:
                return

            # Unsubscribe from EventBus
            self._unsubscribe_from_events()

            # Stop thread pool
            if self._thread_pool is not None:
                self._thread_pool.stop()

            self._running = False

            logger.info("Detection stopped")

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
        # For backward compatibility, return empty list
        return []

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

    def get_detection_stats(self) -> Dict[str, float]:
        """Get detection performance statistics.

        Returns:
            Dict with statistics:
            - detections_per_sec: Detection rate
            - observations_per_sec: Observation rate
            - avg_detection_ms: Average detection time
            - stereo_match_rate: Percentage of detections matched

        Thread-Safe: Returns snapshot of current stats.
        """
        with self._lock:
            if not self._running or self._detection_start_time == 0:
                return {
                    "detections_per_sec": 0.0,
                    "observations_per_sec": 0.0,
                    "avg_detection_ms": 0.0,
                    "stereo_match_rate": 0.0,
                }

            elapsed = __import__('time').time() - self._detection_start_time
            if elapsed == 0:
                elapsed = 0.001  # Avoid division by zero

            return {
                "detections_per_sec": self._detection_count / elapsed,
                "observations_per_sec": self._observation_count / elapsed,
                "avg_detection_ms": 0.0,  # TODO: Track detection timing
                "stereo_match_rate": (
                    (self._observation_count / self._detection_count * 100)
                    if self._detection_count > 0
                    else 0.0
                ),
            }

    def set_lane_rois(
        self,
        lane_rois: Dict[str, List[Tuple[float, float]]],
        plate_rois: Optional[Dict[str, List[Tuple[float, float]]]] = None
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

            # TODO: Rebuild processor with new ROIs
            logger.info(f"Lane ROIs set for cameras: {list(lane_rois.keys())}")

    def is_running(self) -> bool:
        """Check if detection is currently running.

        Returns:
            True if detection threads are active, False otherwise
        """
        with self._lock:
            return self._running

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
        try:
            # Select detector
            detector = self._left_detector if camera_id == "left" else self._right_detector
            if detector is None:
                return []

            # Run detection
            detections = detector.detect(frame)

            # Track stats
            with self._lock:
                self._detection_count += len(detections)

            return detections

        except Exception as e:
            logger.error(f"Detection error for {camera_id}: {e}", exc_info=True)
            return []

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
                self._processor.process_detection_result(camera_id, frame, detections)

        except Exception as e:
            logger.error(f"Error processing stereo result: {e}", exc_info=True)

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
            # Publish each observation to EventBus
            for obs in observations:
                event = ObservationDetectedEvent(
                    observation=obs,
                    timestamp_ns=obs.t_ns,
                    confidence=obs.confidence
                )
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

    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from EventBus events.

        Called when detection stops.
        """
        if not self._subscribed:
            return

        self._event_bus.unsubscribe(FrameCapturedEvent, self._on_frame_captured_internal)

        self._subscribed = False
        logger.info("DetectionService unsubscribed from EventBus")
