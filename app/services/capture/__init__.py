"""Capture service module - Camera management and frame capture.

This module provides camera lifecycle management, frame buffering,
and reconnection handling.
"""

from .interface import CaptureService, FrameCallback, CameraStateCallback
from .implementation import CaptureServiceImpl
from .setup_capture import SetupCaptureJob, SupervisedSetupCaptureService

__all__ = [
    "CameraStateCallback",
    "CaptureService",
    "CaptureServiceImpl",
    "FrameCallback",
    "SetupCaptureJob",
    "SupervisedSetupCaptureService",
]
