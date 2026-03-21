"""Shared data contracts for pitch tracking."""

from .types import (
    Detection,
    Frame,
    PitchMetrics,
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

__all__ = [
    "Detection",
    "Frame",
    "PitchMetrics",
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
]
