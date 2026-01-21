"""DetectionService interface for detection orchestration and stereo matching.

Responsibility: Detect objects in frames, match stereo pairs, generate observations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Tuple

from contracts import Detection, Frame, StereoObservation
from detect.config import DetectorConfig, Mode


# Type alias for callback
ObservationCallback = Callable[[StereoObservation], None]
"""Callback invoked when a stereo observation is detected.

Args:
    observation: Detected stereo observation
"""


class DetectionService(ABC):
    """Abstract interface for detection service.

    Manages detection pipeline:
    - Object detection in frames
    - Stereo matching between camera pairs
    - Lane gating and filtering
    - Observation generation

    Thread-Safety:
        - configure_*() methods are thread-safe
        - process_frame() can be called concurrently from multiple threads
        - Callbacks may be invoked from detection threads
    """

    @abstractmethod
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

        Note: Detector instances are rebuilt on configuration change.
        """

    @abstractmethod
    def configure_threading(self, mode: str, worker_count: int) -> None:
        """Configure detection threading mode.

        Args:
            mode: "per_camera" (one thread per camera) or
                  "worker_pool" (shared thread pool)
            worker_count: Number of worker threads (for worker_pool mode)

        Raises:
            ValueError: If mode is invalid or worker_count <= 0
        """

    @abstractmethod
    def process_frame(self, camera_id: str, frame: Frame) -> List[Detection]:
        """Process a frame and return detections.

        This is typically called from a frame callback, not directly.

        Args:
            camera_id: Camera identifier ("left" or "right")
            frame: Frame to process

        Returns:
            List of detections found in frame

        Thread-Safety: Can be called concurrently from multiple threads.
        Performance: Should return quickly - actual detection runs async.
        """

    @abstractmethod
    def get_latest_detections(self) -> Dict[str, List[Detection]]:
        """Get latest raw detections by camera.

        Returns:
            Dict mapping camera_id to list of detections

        Thread-Safe: Returns snapshot of latest detections.
        """

    @abstractmethod
    def get_latest_gated_detections(self) -> Dict[str, Dict[str, List[Detection]]]:
        """Get latest detections filtered by lane gates.

        Returns:
            Dict mapping camera_id to dict of gate_name to filtered detections
            Example: {
                "left": {"lane": [...], "plate": [...]},
                "right": {"lane": [...], "plate": [...]}
            }

        Thread-Safe: Returns snapshot of latest gated detections.
        """

    @abstractmethod
    def get_latest_observations(self) -> List[StereoObservation]:
        """Get latest stereo observations from matched detections.

        Returns:
            List of stereo observations with 3D positions

        Thread-Safe: Returns snapshot of latest observations.
        """

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
    def is_running(self) -> bool:
        """Check if detection is currently running.

        Returns:
            True if detection threads are active, False otherwise
        """
