"""Configuration loading for pitch tracker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

from configs.validator import validate_config
from exceptions import ConfigError, InvalidConfigError
from log_config.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CameraConfig:
    width: int
    height: int
    fps: int
    pixfmt: str
    exposure_us: int
    gain: float
    wb_mode: Optional[str]
    wb: Optional[int]
    queue_depth: int
    color_mode: bool = True  # Enable color video capture
    flip_left: bool = False  # Rotate left camera 180° (upside down mount)
    flip_right: bool = False  # Rotate right camera 180° (upside down mount)
    rotation_left: float = 0.0  # Software rotation correction (degrees)
    rotation_right: float = 0.0  # Software rotation correction (degrees)
    vertical_offset_px: int = 0  # Vertical alignment offset (pixels)
    alignment_quality: Optional[Dict] = None  # Alignment diagnostics (populated by alignment check)


@dataclass(frozen=True)
class StereoConfig:
    pairing_tolerance_ms: int
    epipolar_epsilon_px: int
    baseline_ft: float
    focal_length_px: float
    cx: Optional[float]
    cy: Optional[float]
    z_min_ft: float
    z_max_ft: float
    max_jump_in: float
    use_frame_index_pairing: bool = False  # Use frame indices instead of timestamps for pairing
    frame_index_tolerance: int = 1  # Allow frame indices to differ by this amount


@dataclass(frozen=True)
class TrackingConfig:
    gate_distance_ft: float
    min_track_frames: int


@dataclass(frozen=True)
class MetricsConfig:
    coordinate_system: str
    plate_plane_z_ft: float
    release_plane_z_ft: float
    approach_window_ft: float
    velo_bounds_mph: Tuple[float, float]
    hb_bounds_in: Tuple[float, float]
    ivb_bounds_in: Tuple[float, float]
    release_height_bounds_ft: Tuple[float, float]


@dataclass(frozen=True)
class RecordingConfig:
    pre_roll_ms: int
    post_roll_ms: int
    output_dir: str
    session_min_active_frames: int
    session_end_gap_frames: int
    # ML training data collection
    save_detections: bool = False
    save_observations: bool = False
    save_training_frames: bool = False
    frame_save_interval: int = 5


@dataclass(frozen=True)
class UiConfig:
    refresh_hz: int


@dataclass(frozen=True)
class TelemetryConfig:
    latency_p95_ms_warn: int


@dataclass(frozen=True)
class DetectorFiltersConfig:
    min_area: int
    max_area: Optional[int]
    min_circularity: float
    max_circularity: Optional[float]
    min_velocity: float
    max_velocity: Optional[float]


@dataclass(frozen=True)
class DetectorConfig:
    type: str
    model_path: Optional[str]
    model_input_size: Tuple[int, int]
    model_conf_threshold: float
    model_class_id: int
    model_format: str
    mode: str
    frame_diff_threshold: float
    bg_diff_threshold: float
    bg_alpha: float
    edge_threshold: float
    blob_threshold: float
    runtime_budget_ms: float
    crop_padding_px: int
    min_consecutive: int
    filters: DetectorFiltersConfig


@dataclass(frozen=True)
class StrikeZoneConfig:
    batter_height_in: float
    top_ratio: float
    bottom_ratio: float
    plate_width_in: float
    plate_length_in: float


@dataclass(frozen=True)
class BallConfig:
    type: str
    radius_in: Dict[str, float]


@dataclass(frozen=True)
class UploadConfig:
    enabled: bool
    swa_api_base: str
    api_key: str


@dataclass(frozen=True)
class AppConfig:
    camera: CameraConfig
    stereo: StereoConfig
    tracking: TrackingConfig
    metrics: MetricsConfig
    recording: RecordingConfig
    ui: UiConfig
    telemetry: TelemetryConfig
    detector: DetectorConfig
    strike_zone: StrikeZoneConfig
    ball: BallConfig
    upload: UploadConfig


def load_config(path: Path) -> AppConfig:
    """Load and validate configuration from YAML file.

    Args:
        path: Path to configuration file

    Returns:
        Validated AppConfig instance

    Raises:
        ConfigError: If configuration is invalid or cannot be loaded
    """
    try:
        logger.info(f"Loading configuration from {path}")
        if not path.exists():
            raise InvalidConfigError(f"Configuration file not found: {path}")

        data = yaml.safe_load(path.read_text())

        # Validate against JSON Schema
        validate_config(data)

        logger.debug("Parsing configuration sections")

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML configuration: {e}")
        raise InvalidConfigError(f"Failed to parse configuration file: {e}")
    except KeyError as e:
        logger.error(f"Missing required configuration key: {e}")
        raise InvalidConfigError(f"Missing required configuration key: {e}")
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid configuration value: {e}")
        raise InvalidConfigError(f"Invalid configuration value: {e}")

    try:
        camera = CameraConfig(**data["camera"])
        stereo_data = data["stereo"]
        stereo = StereoConfig(
            pairing_tolerance_ms=stereo_data["pairing_tolerance_ms"],
            epipolar_epsilon_px=stereo_data["epipolar_epsilon_px"],
            baseline_ft=stereo_data.get("baseline_ft", 1.0),
            focal_length_px=stereo_data.get("focal_length_px", 1200.0),
            cx=stereo_data.get("cx"),
            cy=stereo_data.get("cy"),
            z_min_ft=stereo_data["z_min_ft"],
            z_max_ft=stereo_data["z_max_ft"],
            max_jump_in=stereo_data["max_jump_in"],
        )
        tracking = TrackingConfig(**data["tracking"])
        metrics = MetricsConfig(
            coordinate_system=data["metrics"]["coordinate_system"],
            plate_plane_z_ft=data["metrics"]["plate_plane_z_ft"],
            release_plane_z_ft=data["metrics"]["release_plane_z_ft"],
            approach_window_ft=data["metrics"]["approach_window_ft"],
            velo_bounds_mph=tuple(data["metrics"]["velo_bounds_mph"]),
            hb_bounds_in=tuple(data["metrics"]["hb_bounds_in"]),
            ivb_bounds_in=tuple(data["metrics"]["ivb_bounds_in"]),
            release_height_bounds_ft=tuple(data["metrics"]["release_height_bounds_ft"]),
        )
        recording = RecordingConfig(**data["recording"])
        ui = UiConfig(**data["ui"])
        telemetry = TelemetryConfig(**data["telemetry"])
        detector_filters = DetectorFiltersConfig(**data["detector"]["filters"])
        detector = DetectorConfig(
            type=data["detector"].get("type", "classical"),
            model_path=data["detector"].get("model_path"),
            model_input_size=tuple(data["detector"].get("model_input_size", (640, 640))),
            model_conf_threshold=float(data["detector"].get("model_conf_threshold", 0.25)),
            model_class_id=int(data["detector"].get("model_class_id", 0)),
            model_format=data["detector"].get("model_format", "yolo_v5"),
            mode=data["detector"]["mode"],
            frame_diff_threshold=data["detector"]["frame_diff_threshold"],
            bg_diff_threshold=data["detector"]["bg_diff_threshold"],
            bg_alpha=data["detector"]["bg_alpha"],
            edge_threshold=data["detector"]["edge_threshold"],
            blob_threshold=data["detector"]["blob_threshold"],
            runtime_budget_ms=data["detector"]["runtime_budget_ms"],
            crop_padding_px=data["detector"]["crop_padding_px"],
            min_consecutive=data["detector"]["min_consecutive"],
            filters=detector_filters,
        )
        strike_zone = StrikeZoneConfig(**data["strike_zone"])
        ball = BallConfig(**data["ball"])
        upload = UploadConfig(**data.get("upload", {
            "enabled": False,
            "swa_api_base": "",
            "api_key": "",
        }))

        config = AppConfig(
            camera=camera,
            stereo=stereo,
            tracking=tracking,
            metrics=metrics,
            recording=recording,
            ui=ui,
            telemetry=telemetry,
            detector=detector,
            strike_zone=strike_zone,
            ball=ball,
            upload=upload,
        )

        logger.info(f"Configuration loaded successfully: {config.detector.type} detector, {config.camera.width}x{config.camera.height}@{config.camera.fps}fps")
        return config

    except Exception as e:
        logger.error(f"Failed to construct configuration objects: {e}")
        raise InvalidConfigError(f"Failed to construct configuration: {e}")
