"""Trajectory fitting contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from contracts import StereoObservation, TrackSample
from trajectory.camera_model import CameraModel


class FailureCode(str, Enum):
    INSUFFICIENT_POINTS = "INSUFFICIENT_POINTS"
    ILL_CONDITIONED = "ILL_CONDITIONED"
    TIME_SYNC_SUSPECT = "TIME_SYNC_SUSPECT"
    RADAR_OUTLIER = "RADAR_OUTLIER"
    NO_PLATE_CROSSING = "NO_PLATE_CROSSING"
    NON_MONOTONIC_Z = "NON_MONOTONIC_Z"
    OPT_DID_NOT_CONVERGE = "OPT_DID_NOT_CONVERGE"
    CAMERA_MODEL_MISSING = "CAMERA_MODEL_MISSING"
    REPROJECTION_FAILED = "REPROJECTION_FAILED"


@dataclass(frozen=True)
class ResidualReport:
    t_ns: int
    residual_3d_ft: Optional[float] = None
    residual_px: Optional[float] = None
    normalized_residual: Optional[float] = None
    inlier: bool = True


@dataclass(frozen=True)
class TrajectoryDiagnostics:
    rmse_3d_ft: Optional[float] = None
    rmse_px: Optional[float] = None
    inlier_ratio: Optional[float] = None
    condition_number: Optional[float] = None
    drag_param: Optional[float] = None
    drag_param_ok: Optional[bool] = None
    max_gap_ms: Optional[float] = None
    radar_residual_mph: Optional[float] = None
    radar_inlier_probability: Optional[float] = None
    failure_codes: List[FailureCode] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rmse_3d_ft": self.rmse_3d_ft,
            "rmse_px": self.rmse_px,
            "inlier_ratio": self.inlier_ratio,
            "condition_number": self.condition_number,
            "drag_param": self.drag_param,
            "drag_param_ok": self.drag_param_ok,
            "max_gap_ms": self.max_gap_ms,
            "radar_residual_mph": self.radar_residual_mph,
            "radar_inlier_probability": self.radar_inlier_probability,
            "failure_codes": [code.value for code in self.failure_codes],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class TrajectoryFitRequest:
    observations: List[StereoObservation]
    plate_plane_z_ft: float
    realtime: bool = False
    radar_speed_mph: Optional[float] = None
    radar_speed_ref: Optional[str] = None
    fiducial_time_offset_ns: Optional[int] = None
    time_offset_bounds_ms: float = 5.0
    drag_k0: float = 0.02
    drag_sigma: float = 0.02
    time_offset_sigma_ms: float = 1.0
    max_iter: int = 50
    camera_left: Optional[CameraModel] = None
    camera_right: Optional[CameraModel] = None
    wind_ft_s: Optional[Tuple[float, float, float]] = None


@dataclass(frozen=True)
class TrajectoryFitResult:
    model_name: str
    samples: List[TrackSample]
    plate_crossing_xyz_ft: Optional[Tuple[float, float, float]]
    plate_crossing_t_ns: Optional[int]
    expected_plate_error_ft: Optional[float]
    confidence: float
    diagnostics: TrajectoryDiagnostics
    residuals: List[ResidualReport] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "samples": [sample.__dict__ for sample in self.samples],
            "plate_crossing_xyz_ft": self.plate_crossing_xyz_ft,
            "plate_crossing_t_ns": self.plate_crossing_t_ns,
            "expected_plate_error_ft": self.expected_plate_error_ft,
            "confidence": self.confidence,
            "diagnostics": self.diagnostics.to_dict(),
            "residuals": [residual.__dict__ for residual in self.residuals],
        }
