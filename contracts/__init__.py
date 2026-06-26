"""Shared data contracts for pitch tracking."""

from .types import (
    Detection,
    Frame,
    PitchMetrics,
    RayObservation,
    StereoObservation,
    TrajectoryFit,
    TrajectoryInput,
    TrackSample,
)
from .tooling import (
    AlignmentAnalysisRequest,
    AlignmentAnalysisResult,
    CalibrationRequest,
    CalibrationResult,
    EnvironmentValidationResult,
    TrainingReportRequest,
    TrainingReportResult,
)
from .setup import (
    CalibrationQualityReport,
    CoarseRectificationResult,
    ExposureLockResult,
    FocusLockResult,
    StereoCalibrationProfile,
    StereoOverlapResult,
    SyncCheckResult,
)

__all__ = [
    "Detection",
    "Frame",
    "PitchMetrics",
    "RayObservation",
    "StereoObservation",
    "TrajectoryFit",
    "TrajectoryInput",
    "TrackSample",
    "AlignmentAnalysisRequest",
    "AlignmentAnalysisResult",
    "CalibrationRequest",
    "CalibrationResult",
    "EnvironmentValidationResult",
    "TrainingReportRequest",
    "TrainingReportResult",
    "SyncCheckResult",
    "FocusLockResult",
    "ExposureLockResult",
    "StereoOverlapResult",
    "CoarseRectificationResult",
    "StereoCalibrationProfile",
    "CalibrationQualityReport",
]
