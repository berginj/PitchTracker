"""Service layer for PitchTracker application.

This module defines the service interfaces that separate concerns into
clear, testable components with single responsibilities:

├── capture/     - Camera management and frame capture
├── detection/   - Detection orchestration and stereo matching
├── recording/   - Async recording of frames and metadata
└── analysis/    - Post-processing and pattern detection

Each service module contains:
- interface.py: Abstract base class defining the contract
- implementation.py: Concrete implementation (to be added)
"""

from .capture import CaptureService, FrameCallback, CameraStateCallback
from .detection import DetectionService, ObservationCallback
from .recording import RecordingService, RecordingCallback
from .analysis import AnalysisService
from .tooling import ToolingService, SubprocessToolingService, get_tooling_service
from .rig_profile import (
    CRITICAL,
    PASS,
    WARN,
    RigProfile,
    RigProfileService,
    RigProfileValidation,
)

__all__ = [
    # Capture service
    "CaptureService",
    "FrameCallback",
    "CameraStateCallback",
    # Detection service
    "DetectionService",
    "ObservationCallback",
    # Recording service
    "RecordingService",
    "RecordingCallback",
    # Analysis service
    "AnalysisService",
    # Tooling service
    "ToolingService",
    "SubprocessToolingService",
    "get_tooling_service",
    # Rig profile service
    "CRITICAL",
    "PASS",
    "WARN",
    "RigProfile",
    "RigProfileService",
    "RigProfileValidation",
]
