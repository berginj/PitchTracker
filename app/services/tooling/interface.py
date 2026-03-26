"""Interface for process-backed tooling workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod

from contracts.tooling import (
    AlignmentAnalysisRequest,
    AlignmentAnalysisResult,
    CalibrationRequest,
    CalibrationResult,
    EnvironmentValidationResult,
    TrainingReportRequest,
    TrainingReportResult,
)


class ToolingService(ABC):
    """Boundary for heavyweight tooling tasks that should not run in the UI process."""

    @abstractmethod
    def validate_environment(self) -> EnvironmentValidationResult:
        """Run environment validation in a worker process."""

    @abstractmethod
    def build_training_report(self, request: TrainingReportRequest) -> TrainingReportResult:
        """Build a training report in a worker process."""

    @abstractmethod
    def run_calibration(self, request: CalibrationRequest) -> CalibrationResult:
        """Run stereo calibration in a worker process."""

    @abstractmethod
    def analyze_alignment(self, request: AlignmentAnalysisRequest) -> AlignmentAnalysisResult:
        """Analyze camera alignment in a worker process."""
