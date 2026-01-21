"""Service layer for PitchTracker application.

This module defines the service interfaces that separate concerns:
- CaptureService: Camera management and frame capture
- DetectionService: Detection orchestration and stereo matching
- RecordingService: Async recording of frames and metadata
- AnalysisService: Post-processing and pattern detection
- PipelineOrchestrator: Composes services and manages state
"""

from .capture_service import CaptureService, FrameCallback
from .detection_service import DetectionService, ObservationCallback
from .recording_service import RecordingService, RecordingCallback
from .analysis_service import AnalysisService

__all__ = [
    "CaptureService",
    "DetectionService",
    "RecordingService",
    "AnalysisService",
    "FrameCallback",
    "ObservationCallback",
    "RecordingCallback",
]
