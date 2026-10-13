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

from importlib import import_module
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .capture import CaptureService, FrameCallback, CameraStateCallback
    from .detection import DetectionService, ObservationCallback
    from .recording import RecordingService, RecordingCallback
    from .analysis import AnalysisService
    from .tooling import ToolingService, SubprocessToolingService, get_tooling_service
    from .rig_profile import CRITICAL, PASS, WARN, RigProfile, RigProfileService, RigProfileValidation

_MODULE_BY_NAME = {
    name: module for module, names in {
        "capture": ("CaptureService", "FrameCallback", "CameraStateCallback"),
        "detection": ("DetectionService", "ObservationCallback"),
        "recording": ("RecordingService", "RecordingCallback"),
        "analysis": ("AnalysisService",),
        "tooling": ("ToolingService", "SubprocessToolingService", "get_tooling_service"),
        "rig_profile": ("CRITICAL", "PASS", "WARN", "RigProfile", "RigProfileService", "RigProfileValidation"),
    }.items() for name in names
}


def __getattr__(name: str) -> Any:
    """Resolve public exports without importing every concrete service."""
    module = _MODULE_BY_NAME.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


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
