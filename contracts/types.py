"""Core data contracts for capture, detection, stereo, tracking, and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class Frame:
    camera_id: str
    frame_index: int
    t_capture_monotonic_ns: int
    image: Any
    width: int
    height: int
    pixfmt: str


@dataclass(frozen=True)
class Detection:
    camera_id: str
    frame_index: int
    t_capture_monotonic_ns: int
    u: float
    v: float
    radius_px: float
    confidence: float


@dataclass(frozen=True)
class StereoObservation:
    t_ns: int
    left: Tuple[float, float]
    right: Tuple[float, float]
    X: float
    Y: float
    Z: float
    quality: float
    covariance: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = None
    confidence: float = 0.0


@dataclass(frozen=True)
class TrackSample:
    t_ns: int
    X: float
    Y: float
    Z: float
    Vx: float
    Vy: float
    Vz: float
    Ax: Optional[float] = None
    Ay: Optional[float] = None
    Az: Optional[float] = None
    quality_flags: int = 0


@dataclass(frozen=True)
class TrajectoryInput:
    observations: list[StereoObservation]
    radar_speed_mph: Optional[float] = None
    pitch_id: Optional[str] = None
    t_start_ns: Optional[int] = None
    t_end_ns: Optional[int] = None


@dataclass(frozen=True)
class TrajectoryFit:
    model_name: str
    samples: list[TrackSample]
    crossing_xyz_ft: Optional[Tuple[float, float, float]]
    confidence: float
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PitchMetrics:
    pitch_id: str
    t_start_ns: int
    t_end_ns: int
    velo_mph: float
    HB_in: float
    iVB_in: float
    release_xyz_ft: Tuple[float, float, float]
    approach_angles_deg: Tuple[float, float]
    confidence: float
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    latency: Dict[str, Any] = field(default_factory=dict)
