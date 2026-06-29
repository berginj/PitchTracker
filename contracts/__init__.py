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
from .catalog import (
    CameraCapabilities,
    CameraCatalogEntry,
    CameraMode,
    KnownDevice,
    KnownGoodSettings,
)
from .evidence import (
    Candidate2DEvidence,
    Observation3DEvidence,
    PitchVerdictEvidence,
    StereoMatchEvidence,
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
    "CameraMode",
    "CameraCapabilities",
    "KnownGoodSettings",
    "CameraCatalogEntry",
    "KnownDevice",
    "Candidate2DEvidence",
    "StereoMatchEvidence",
    "Observation3DEvidence",
    "PitchVerdictEvidence",
]
