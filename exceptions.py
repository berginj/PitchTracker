"""Custom exception classes for PitchTracker."""

from __future__ import annotations

from typing import Optional


class PitchTrackerError(Exception):
    """Base exception for all PitchTracker errors."""

    pass


class CameraError(PitchTrackerError):
    """Base exception for camera-related errors."""

    def __init__(self, message: str, camera_id: Optional[str] = None):
        self.camera_id = camera_id
        super().__init__(message)


class CameraConnectionError(CameraError):
    """Raised when camera connection fails or is lost."""

    pass


class CameraConfigurationError(CameraError):
    """Raised when camera configuration fails."""

    pass


class CameraNotFoundError(CameraError):
    """Raised when a specified camera is not found."""

    pass


class CalibrationError(PitchTrackerError):
    """Base exception for calibration-related errors."""

    pass


class InvalidROIError(CalibrationError):
    """Raised when ROI configuration is invalid."""

    pass


class CheckerboardNotFoundError(CalibrationError):
    """Raised when checkerboard pattern cannot be detected."""

    pass


class ConfigError(PitchTrackerError):
    """Base exception for configuration errors."""

    pass


class InvalidConfigError(ConfigError):
    """Raised when configuration file is invalid or corrupted."""

    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration fails schema validation."""

    def __init__(self, message: str, validation_errors: Optional[list] = None):
        self.validation_errors = validation_errors or []
        super().__init__(message)


class DetectionError(PitchTrackerError):
    """Base exception for detection-related errors."""

    pass


class ModelLoadError(DetectionError):
    """Raised when ML model fails to load."""

    pass


class ModelInferenceError(DetectionError):
    """Raised when ML model inference fails."""

    pass


class StereoError(PitchTrackerError):
    """Base exception for stereo-related errors."""

    pass


class TriangulationError(StereoError):
    """Raised when stereo triangulation fails."""

    pass


class RecordingError(PitchTrackerError):
    """Base exception for recording-related errors."""

    pass


class DiskSpaceError(RecordingError):
    """Raised when insufficient disk space is available."""

    pass


class FileWriteError(RecordingError):
    """Raised when file write operation fails."""

    pass
