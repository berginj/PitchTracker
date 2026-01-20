"""Pipeline initialization logic for cameras, detectors, stereo, and ROIs."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from capture import CameraDevice
from configs.lane_io import load_lane_rois
from configs.roi_io import load_rois
from configs.settings import AppConfig
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig
from detect.config import FilterConfig, Mode
from detect.lane import LaneGate, LaneRoi
from detect.ml_detector import MlDetector
from stereo import StereoLaneGate
from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry


class PipelineInitializer:
    """Handles one-time initialization of pipeline components.

    Manages detector configuration, builds detectors, initializes stereo
    matcher, loads ROIs, and configures cameras.
    """

    def __init__(self) -> None:
        """Initialize with default detector configuration."""
        self._detector_config = CvDetectorConfig()
        self._detector_mode = Mode.MODE_A
        self._detector_type = "classical"
        self._detector_model_path: Optional[str] = None
        self._detector_model_input_size: Tuple[int, int] = (640, 640)
        self._detector_model_conf_threshold = 0.25
        self._detector_model_class_id = 0
        self._detector_model_format = "yolo_v5"

    @staticmethod
    def configure_camera(camera: CameraDevice, config: AppConfig, is_left: bool = True) -> None:
        """Configure camera mode and controls.

        Args:
            camera: Camera device to configure
            config: Application configuration with camera settings
            is_left: True for left camera, False for right camera
        """
        # Determine pixel format based on color_mode setting
        pixfmt = config.camera.pixfmt
        if config.camera.color_mode:
            # Override to color format when color_mode is enabled
            pixfmt = "YUYV" if pixfmt == "GRAY8" else pixfmt

        # Select flip setting based on which camera this is
        flip_180 = config.camera.flip_left if is_left else config.camera.flip_right

        camera.set_mode(
            config.camera.width,
            config.camera.height,
            config.camera.fps,
            pixfmt,
            flip_180=flip_180,
        )
        camera.set_controls(
            config.camera.exposure_us,
            config.camera.gain,
            config.camera.wb_mode,
            config.camera.wb,
        )

    @staticmethod
    def load_rois(
        left_id: str, right_id: str
    ) -> Tuple[
        Optional[list[tuple[float, float]]],
        Optional[LaneGate],
        Optional[StereoLaneGate],
        Optional[LaneGate],
        Optional[StereoLaneGate],
    ]:
        """Load ROIs from config files.

        Loads lane and plate ROIs from roi.json and lane_roi.json config files.

        Args:
            left_id: Left camera serial number
            right_id: Right camera serial number

        Returns:
            Tuple of (lane_polygon, lane_gate, stereo_gate, plate_gate, plate_stereo_gate)
        """
        rois = load_rois(Path("configs/roi.json"))
        lane = rois.get("lane")
        plate = rois.get("plate")
        lane_rois = load_lane_rois(Path("configs/lane_roi.json"))

        lane_polygon = None
        lane_gate = None
        stereo_gate = None
        plate_gate = None
        plate_stereo_gate = None

        # Load lane ROI
        if lane:
            lane_polygon = [(float(x), float(y)) for x, y in lane]
            lane_roi_left = LaneRoi(polygon=[(float(x), float(y)) for x, y in lane])
            lane_roi_right = lane_roi_left

            # Check for per-camera lane ROIs
            if lane_rois:
                lane_left = lane_rois.get(left_id) or lane_rois.get("left")
                lane_right = lane_rois.get(right_id) or lane_rois.get("right")
                if lane_left is not None:
                    lane_roi_left = lane_left
                if lane_right is not None:
                    lane_roi_right = lane_right

            lane_gate = LaneGate(roi_by_camera={left_id: lane_roi_left, right_id: lane_roi_right})
            stereo_gate = StereoLaneGate(lane_gate=lane_gate)

        # Load plate ROI
        if plate:
            plate_roi = LaneRoi(polygon=[(float(x), float(y)) for x, y in plate])
            plate_gate = LaneGate(roi_by_camera={left_id: plate_roi, right_id: plate_roi})
            plate_stereo_gate = StereoLaneGate(lane_gate=plate_gate)

        return lane_polygon, lane_gate, stereo_gate, plate_gate, plate_stereo_gate

    @staticmethod
    def create_stereo_matcher(config: AppConfig) -> SimpleStereoMatcher:
        """Create stereo matcher from config.

        Args:
            config: Application configuration with stereo settings

        Returns:
            Initialized SimpleStereoMatcher
        """
        cx = config.stereo.cx
        cy = config.stereo.cy
        if cx is None:
            cx = config.camera.width / 2.0
        if cy is None:
            cy = config.camera.height / 2.0

        geometry = StereoGeometry(
            baseline_ft=config.stereo.baseline_ft,
            focal_length_px=config.stereo.focal_length_px,
            cx=float(cx),
            cy=float(cy),
            epipolar_epsilon_px=float(config.stereo.epipolar_epsilon_px),
            z_min_ft=float(config.stereo.z_min_ft),
            z_max_ft=float(config.stereo.z_max_ft),
        )
        return SimpleStereoMatcher(geometry)

    def initialize_detector_config(self, config: AppConfig) -> None:
        """Initialize detector configuration from app config.

        Args:
            config: Application configuration with detector settings
        """
        cfg = config.detector
        self._detector_type = cfg.type
        self._detector_model_path = cfg.model_path
        self._detector_model_input_size = cfg.model_input_size
        self._detector_model_conf_threshold = cfg.model_conf_threshold
        self._detector_model_class_id = cfg.model_class_id
        self._detector_model_format = cfg.model_format

        filter_cfg = FilterConfig(
            min_area=cfg.filters.min_area,
            max_area=cfg.filters.max_area,
            min_circularity=cfg.filters.min_circularity,
            max_circularity=cfg.filters.max_circularity,
            min_velocity=cfg.filters.min_velocity,
            max_velocity=cfg.filters.max_velocity,
        )
        detector_cfg = CvDetectorConfig(
            frame_diff_threshold=cfg.frame_diff_threshold,
            bg_diff_threshold=cfg.bg_diff_threshold,
            bg_alpha=cfg.bg_alpha,
            edge_threshold=cfg.edge_threshold,
            blob_threshold=cfg.blob_threshold,
            runtime_budget_ms=cfg.runtime_budget_ms,
            crop_padding_px=cfg.crop_padding_px,
            min_consecutive=cfg.min_consecutive,
            filters=filter_cfg,
        )
        self._detector_config = detector_cfg
        self._detector_mode = Mode(cfg.mode)

    def update_detector_config(
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
        """Update detector configuration at runtime.

        Args:
            config: Detector configuration
            mode: Detection mode
            detector_type: Type of detector ("classical" or "ml")
            model_path: Path to ML model (for ML detector)
            model_input_size: Model input size (for ML detector)
            model_conf_threshold: Confidence threshold (for ML detector)
            model_class_id: Class ID to detect (for ML detector)
            model_format: Model format (for ML detector)
        """
        self._detector_config = config
        self._detector_mode = mode
        self._detector_type = detector_type
        self._detector_model_path = model_path
        self._detector_model_input_size = model_input_size
        self._detector_model_conf_threshold = model_conf_threshold
        self._detector_model_class_id = model_class_id
        self._detector_model_format = model_format

    def build_detectors(
        self, left_id: str, right_id: str, lane_polygon: Optional[list[tuple[float, float]]]
    ) -> Dict[str, object]:
        """Build detectors for both cameras.

        Args:
            left_id: Left camera serial number
            right_id: Right camera serial number
            lane_polygon: Optional lane polygon for classical detector ROI

        Returns:
            Dictionary mapping camera labels to detector instances
        """
        detectors: Dict[str, object] = {}
        detectors["left"] = self._build_detector_for_camera(left_id, lane_polygon)
        detectors["right"] = self._build_detector_for_camera(right_id, lane_polygon)
        return detectors

    def _build_detector_for_camera(
        self, camera_id: str, lane_polygon: Optional[list[tuple[float, float]]]
    ) -> object:
        """Build detector for a single camera.

        Args:
            camera_id: Camera serial number
            lane_polygon: Optional lane polygon for classical detector ROI

        Returns:
            Detector instance (ClassicalDetector or MlDetector)
        """
        if self._detector_type == "ml":
            return MlDetector(
                model_path=self._detector_model_path,
                input_size=self._detector_model_input_size,
                conf_threshold=self._detector_model_conf_threshold,
                class_id=self._detector_model_class_id,
                output_format=self._detector_model_format,
            )

        roi_by_camera = {}
        if lane_polygon:
            roi_by_camera = {camera_id: lane_polygon}

        return ClassicalDetector(
            config=self._detector_config,
            mode=self._detector_mode,
            roi_by_camera=roi_by_camera,
        )

    def warmup_detectors(self, detectors: Dict[str, object], config: AppConfig) -> None:
        """Warm up detectors with dummy frame.

        Runs detectors once with a dummy frame to initialize any lazy-loaded
        resources (especially important for ML models).

        Args:
            detectors: Dictionary of detector instances
            config: Application configuration with camera dimensions
        """
        height = config.camera.height
        width = config.camera.width
        dummy = np.zeros((height, width), dtype=np.uint8)

        for label, detector in detectors.items():
            frame = Frame(
                camera_id=label,
                frame_index=0,
                t_capture_monotonic_ns=0,
                image=dummy,
                width=width,
                height=height,
                pixfmt=config.camera.pixfmt,
            )
            try:
                detector.detect(frame)
            except Exception:
                # Warm-up failures are non-fatal
                continue
