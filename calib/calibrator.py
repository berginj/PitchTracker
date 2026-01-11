"""Calibration interfaces for intrinsics and stereo geometry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class IntrinsicsResult:
    camera_id: str
    camera_matrix: Any
    distortion_coeffs: Any
    reprojection_error_px: float


@dataclass(frozen=True)
class StereoCalibrationResult:
    left_camera_id: str
    right_camera_id: str
    rotation: Any
    translation: Any
    essential_matrix: Any
    fundamental_matrix: Any
    reprojection_error_px: float


class Calibrator(ABC):
    @abstractmethod
    def calibrate_intrinsics(self, frames: Dict[str, Any]) -> IntrinsicsResult:
        """Compute camera intrinsics from calibration frames."""

    @abstractmethod
    def calibrate_stereo(self, frames: Dict[str, Any]) -> StereoCalibrationResult:
        """Compute stereo calibration from paired frames."""
