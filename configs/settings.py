"""Configuration loading for pitch tracker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import yaml


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


@dataclass(frozen=True)
class UiConfig:
    refresh_hz: int


@dataclass(frozen=True)
class TelemetryConfig:
    latency_p95_ms_warn: int


@dataclass(frozen=True)
class AppConfig:
    camera: CameraConfig
    stereo: StereoConfig
    tracking: TrackingConfig
    metrics: MetricsConfig
    recording: RecordingConfig
    ui: UiConfig
    telemetry: TelemetryConfig


def load_config(path: Path) -> AppConfig:
    data = yaml.safe_load(path.read_text())
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
    return AppConfig(
        camera=camera,
        stereo=stereo,
        tracking=tracking,
        metrics=metrics,
        recording=recording,
        ui=ui,
        telemetry=telemetry,
    )
