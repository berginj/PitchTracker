"""Pipeline initialization logic for cameras, detectors, stereo, and ROIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np

from capture import CameraDevice
from configs.roi_io import load_runtime_roi_maps
from configs.settings import AppConfig
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig
from detect.config import FilterConfig, Mode
from detect.detector import Detector
from detect.lane import LaneGate, LaneRoi
from detect.ml_detector import MlDetector
from exceptions import CameraConfigurationError
from log_config.logger import get_logger
from stereo import CalibratedStereoGeometry, CalibratedStereoMatcher, StereoLaneGate, StereoMatcher
from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry

logger = get_logger(__name__)


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

        # Select transform settings based on which camera this is.
        flip_180 = config.camera.flip_left if is_left else config.camera.flip_right
        rotation_correction = config.camera.rotation_left if is_left else config.camera.rotation_right
        vertical_offset_px = 0 if is_left else config.camera.vertical_offset_px

        camera.set_mode(
            config.camera.width,
            config.camera.height,
            config.camera.fps,
            pixfmt,
            flip_180=flip_180,
            rotation_correction=rotation_correction,
            vertical_offset_px=vertical_offset_px,
        )
        camera.set_controls(
            config.camera.exposure_us,
            config.camera.gain,
            config.camera.wb_mode,
            config.camera.wb,
        )

    @staticmethod
    def verify_camera_configuration(camera: CameraDevice, config: AppConfig) -> dict[str, Any]:
        """Fail closed when a physical camera cannot prove its negotiated state."""
        mode = camera.get_mode()
        controls = camera.get_controls()
        failures: list[str] = []

        if not isinstance(mode, Mapping):
            failures.append("negotiated mode readback is unavailable")
        else:
            expected_pixfmt = config.camera.pixfmt
            if config.camera.color_mode and expected_pixfmt == "GRAY8":
                expected_pixfmt = "YUYV"
            actual_pixfmt = str(mode.get("pixfmt") or "").upper()
            if actual_pixfmt == "YUY2":
                actual_pixfmt = "YUYV"
            expected = {
                "width": int(config.camera.width),
                "height": int(config.camera.height),
                "pixfmt": str(expected_pixfmt).upper(),
            }
            for key, expected_value in expected.items():
                actual_value = mode.get(key) if key != "pixfmt" else actual_pixfmt
                if actual_value != expected_value:
                    failures.append(f"{key} expected {expected_value!r}, read back {actual_value!r}")
            try:
                fps_value = mode.get("fps")
                if not isinstance(fps_value, (str, bytes, int, float)):
                    raise TypeError("fps readback is not numeric")
                actual_fps = float(fps_value)
            except (TypeError, ValueError):
                actual_fps = 0.0
            fps_tolerance = max(0.5, float(config.camera.fps) * 0.02)
            if abs(actual_fps - float(config.camera.fps)) > fps_tolerance:
                failures.append(f"fps expected {config.camera.fps!r}, read back {actual_fps!r}")

        if not isinstance(controls, Mapping):
            failures.append("control readback is unavailable")
        else:
            if controls.get("readback_verified") is not True:
                failures.append(str(controls.get("readback_note") or "control readback was not verified"))
            for key, label in (
                ("auto_exposure_disabled", "automatic exposure"),
                ("auto_white_balance_disabled", "automatic white balance"),
                ("autofocus_disabled", "autofocus"),
            ):
                if controls.get(key) is not True:
                    failures.append(f"{label} is not verified disabled")

        if failures:
            raise CameraConfigurationError("Physical camera configuration verification failed: " + "; ".join(failures))
        return {
            "mode": dict(mode) if isinstance(mode, Mapping) else {},
            "controls": dict(controls) if isinstance(controls, Mapping) else {},
        }

    @staticmethod
    def load_rois(
        left_id: str,
        right_id: str,
        roi_path: Path = Path("configs/roi.json"),
        lane_path: Path = Path("configs/lane_roi.json"),
    ) -> Tuple[
        Optional[list[tuple[float, float]]],
        Optional[LaneGate],
        Optional[StereoLaneGate],
        Optional[LaneGate],
        Optional[StereoLaneGate],
    ]:
        """Load ROIs from config files.

        Loads lane and plate ROIs from active rig-profile or legacy ROI files.

        Args:
            left_id: Left camera serial number
            right_id: Right camera serial number

        Returns:
            Tuple of (lane_polygon, lane_gate, stereo_gate, plate_gate, plate_stereo_gate)
        """
        lane_rois, plate_rois = load_runtime_roi_maps(roi_path, left_id, right_id, lane_path=lane_path)

        lane_polygon = None
        lane_gate = None
        stereo_gate = None
        plate_gate = None
        plate_stereo_gate = None

        if lane_rois:
            left_lane = lane_rois.get(left_id) or lane_rois.get("left")
            right_lane = lane_rois.get(right_id) or lane_rois.get("right")
            first_lane = left_lane or right_lane
            if first_lane:
                lane_polygon = [(float(x), float(y)) for x, y in first_lane]
            roi_by_camera = {}
            if left_lane:
                roi_by_camera[left_id] = LaneRoi(polygon=[(float(x), float(y)) for x, y in left_lane])
            if right_lane:
                roi_by_camera[right_id] = LaneRoi(polygon=[(float(x), float(y)) for x, y in right_lane])
            lane_gate = LaneGate(roi_by_camera=roi_by_camera)
            stereo_gate = StereoLaneGate(lane_gate=lane_gate)

        if plate_rois:
            plate_gate = LaneGate(
                roi_by_camera={
                    camera_id: LaneRoi(polygon=[(float(x), float(y)) for x, y in points])
                    for camera_id, points in plate_rois.items()
                }
            )
            plate_stereo_gate = StereoLaneGate(lane_gate=plate_gate)

        return lane_polygon, lane_gate, stereo_gate, plate_gate, plate_stereo_gate

    @staticmethod
    def create_stereo_matcher(
        config: AppConfig,
        calibration_path: Path = Path("calibration/stereo_calibration.npz"),
        allow_non_production_calibration: bool = False,
    ) -> StereoMatcher:
        """Create stereo matcher from config.

        A saved calibration is only used for live tracking when it is marked
        ``production_ready`` (full calibration), unless
        ``allow_non_production_calibration`` is set. Quick-mode calibrations are
        for setup feedback only and must not silently drive triangulation.

        Args:
            config: Application configuration with stereo settings
            calibration_path: Path to the stereo calibration NPZ
            allow_non_production_calibration: Permit non-production NPZ files

        Returns:
            Initialized stereo matcher (calibrated when a valid NPZ exists)
        """
        if calibration_path.exists() and PipelineInitializer._calibration_is_usable(
            calibration_path, allow_non_production_calibration
        ):
            calibrated_geometry = CalibratedStereoGeometry.from_npz(
                calibration_path,
                epipolar_epsilon_px=float(config.stereo.epipolar_epsilon_px),
                z_min_ft=float(config.stereo.z_min_ft),
                z_max_ft=float(config.stereo.z_max_ft),
                time_sync_offset_ns=int(config.stereo.time_sync_offset_ns),
            )
            return CalibratedStereoMatcher(calibrated_geometry)

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
            time_sync_offset_ns=int(config.stereo.time_sync_offset_ns),
        )
        return SimpleStereoMatcher(geometry)

    @staticmethod
    def _calibration_is_usable(calibration_path: Path, allow_non_production: bool) -> bool:
        """Return True when the saved calibration may drive live triangulation.

        Legacy NPZ files without a ``production_ready`` flag are treated as
        usable for backward compatibility. Files explicitly marked
        non-production (quick-mode) are rejected unless ``allow_non_production``
        is set.
        """
        if allow_non_production:
            return True
        try:
            data = np.load(calibration_path, allow_pickle=True)
        except Exception as exc:
            logger.warning("Could not read calibration {}: {}", calibration_path, exc)
            return False
        if "production_ready" not in data:
            return True
        production_ready = bool(data["production_ready"])
        if not production_ready:
            logger.warning(
                "Ignoring non-production (quick-mode) calibration {} for live "
                "tracking; run a full calibration or pass "
                "allow_non_production_calibration=True.",
                calibration_path,
            )
        return production_ready

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

        detector_cfg = self.cv_detector_config(config)
        self._detector_config = detector_cfg
        self._detector_mode = Mode(cfg.mode)

    @staticmethod
    def cv_detector_config(config: AppConfig) -> CvDetectorConfig:
        """Translate application settings into the detector's runtime contract."""
        cfg = config.detector
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
        return detector_cfg

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
    ) -> Dict[str, Detector]:
        """Build detectors for both cameras.

        Args:
            left_id: Left camera serial number
            right_id: Right camera serial number
            lane_polygon: Optional lane polygon for classical detector ROI

        Returns:
            Dictionary mapping camera labels to detector instances
        """
        detectors: Dict[str, Detector] = {}
        detectors["left"] = self._build_detector_for_camera(left_id, lane_polygon)
        detectors["right"] = self._build_detector_for_camera(right_id, lane_polygon)
        return detectors

    def _build_detector_for_camera(self, camera_id: str, lane_polygon: Optional[list[tuple[float, float]]]) -> Detector:
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

    def warmup_detectors(self, detectors: Dict[str, Detector], config: AppConfig) -> None:
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
