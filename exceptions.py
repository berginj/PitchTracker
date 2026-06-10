"""Custom exception classes for PitchTracker."""

from __future__ import annotations

from typing import Optional


class PitchTrackerError(Exception):
    """Base exception for all PitchTracker errors."""



class CameraError(PitchTrackerError):
    """Base exception for camera-related errors."""

    def __init__(self, message: str, camera_id: Optional[str] = None):
        self.camera_id = camera_id
        super().__init__(message)


class CameraConnectionError(CameraError):
    """Raised when camera connection fails or is lost."""



class CameraConfigurationError(CameraError):
    """Raised when camera configuration fails."""



class CameraNotFoundError(CameraError):
    """Raised when a specified camera is not found."""



class CalibrationError(PitchTrackerError):
    """Base exception for calibration-related errors."""



class InvalidROIError(CalibrationError):
    """Raised when ROI configuration is invalid."""



class CheckerboardNotFoundError(CalibrationError):
    """Raised when checkerboard pattern cannot be detected."""



class CalibrationInputError(CalibrationError):
    """Raised when calibration inputs are invalid or incomplete."""



class CalibrationExecutionError(CalibrationError):
    """Raised when the calibration worker fails during execution."""



class CalibrationPersistenceError(CalibrationError):
    """Raised when calibration results cannot be written to disk."""



class ConfigError(PitchTrackerError):
    """Base exception for configuration errors."""



class InvalidConfigError(ConfigError):
    """Raised when configuration file is invalid or corrupted."""



class ConfigValidationError(ConfigError):
    """Raised when configuration fails schema validation."""

    def __init__(self, message: str, validation_errors: Optional[list] = None):
        self.validation_errors = validation_errors or []
        super().__init__(message)


class DetectionError(PitchTrackerError):
    """Base exception for detection-related errors."""



class ModelLoadError(DetectionError):
    """Raised when ML model fails to load."""



class ModelInferenceError(DetectionError):
    """Raised when ML model inference fails."""



class StereoError(PitchTrackerError):
    """Base exception for stereo-related errors."""



class TriangulationError(StereoError):
    """Raised when stereo triangulation fails."""



class RecordingError(PitchTrackerError):
    """Base exception for recording-related errors."""



class DiskSpaceError(RecordingError):
    """Raised when insufficient disk space is available."""



class FileWriteError(RecordingError):
    """Raised when file write operation fails."""

