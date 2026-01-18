"""Configuration validation for ensuring valid app settings."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Configuration validation error."""

    field: str
    message: str
    severity: str = "error"  # "error", "warning", "info"


class ConfigValidator:
    """Validates application configuration."""

    def __init__(self):
        """Initialize config validator."""
        self._errors: List[ValidationError] = []
        self._warnings: List[ValidationError] = []

    def validate(self, config) -> tuple[bool, List[ValidationError]]:
        """Validate configuration.

        Args:
            config: App configuration to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        self._errors = []
        self._warnings = []

        # Camera configuration
        self._validate_camera_config(config)

        # Recording configuration
        self._validate_recording_config(config)

        # Paths
        self._validate_paths(config)

        # Detection configuration
        self._validate_detection_config(config)

        # Calibration
        self._validate_calibration(config)

        # Combine errors and warnings
        all_issues = self._errors + self._warnings
        is_valid = len(self._errors) == 0

        if not is_valid:
            logger.error(f"Configuration validation failed with {len(self._errors)} errors")
        elif len(self._warnings) > 0:
            logger.warning(f"Configuration validation passed with {len(self._warnings)} warnings")
        else:
            logger.info("Configuration validation passed")

        return is_valid, all_issues

    def _validate_camera_config(self, config) -> None:
        """Validate camera configuration."""
        try:
            # Resolution
            if config.camera.width <= 0:
                self._errors.append(ValidationError(
                    "camera.width",
                    f"Camera width must be positive, got {config.camera.width}"
                ))

            if config.camera.height <= 0:
                self._errors.append(ValidationError(
                    "camera.height",
                    f"Camera height must be positive, got {config.camera.height}"
                ))

            # Common resolutions check
            common_resolutions = [(640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]
            if (config.camera.width, config.camera.height) not in common_resolutions:
                self._warnings.append(ValidationError(
                    "camera.resolution",
                    f"Unusual resolution {config.camera.width}x{config.camera.height}. "
                    f"Common resolutions are: {common_resolutions}",
                    severity="warning"
                ))

            # FPS
            if config.camera.fps <= 0:
                self._errors.append(ValidationError(
                    "camera.fps",
                    f"Camera FPS must be positive, got {config.camera.fps}"
                ))
            elif config.camera.fps > 120:
                self._warnings.append(ValidationError(
                    "camera.fps",
                    f"Very high FPS ({config.camera.fps}). System may not keep up.",
                    severity="warning"
                ))

            # Exposure
            if hasattr(config.camera, 'exposure') and config.camera.exposure < 0:
                self._warnings.append(ValidationError(
                    "camera.exposure",
                    "Negative exposure may cause issues",
                    severity="warning"
                ))

        except AttributeError as e:
            self._errors.append(ValidationError(
                "camera",
                f"Missing required camera configuration: {e}"
            ))

    def _validate_recording_config(self, config) -> None:
        """Validate recording configuration."""
        try:
            if hasattr(config, 'recording'):
                # Quality/bitrate
                if hasattr(config.recording, 'quality'):
                    quality = config.recording.quality
                    if quality < 0 or quality > 100:
                        self._errors.append(ValidationError(
                            "recording.quality",
                            f"Recording quality must be 0-100, got {quality}"
                        ))

                # Buffer size
                if hasattr(config.recording, 'buffer_size'):
                    if config.recording.buffer_size < 1:
                        self._errors.append(ValidationError(
                            "recording.buffer_size",
                            f"Buffer size must be positive, got {config.recording.buffer_size}"
                        ))
                    elif config.recording.buffer_size > 100:
                        self._warnings.append(ValidationError(
                            "recording.buffer_size",
                            f"Very large buffer size ({config.recording.buffer_size}) may use excessive memory",
                            severity="warning"
                        ))

        except AttributeError:
            # Recording config may be optional
            pass

    def _validate_paths(self, config) -> None:
        """Validate file paths."""
        try:
            # Calibration file
            if hasattr(config, 'calibration_file'):
                calib_path = Path(config.calibration_file)
                if not calib_path.exists():
                    self._warnings.append(ValidationError(
                        "calibration_file",
                        f"Calibration file does not exist: {calib_path}",
                        severity="warning"
                    ))

            # Model paths
            if hasattr(config, 'model') and hasattr(config.model, 'path'):
                model_path = Path(config.model.path)
                if not model_path.exists():
                    self._errors.append(ValidationError(
                        "model.path",
                        f"Model file does not exist: {model_path}"
                    ))

        except Exception as e:
            self._warnings.append(ValidationError(
                "paths",
                f"Error validating paths: {e}",
                severity="warning"
            ))

    def _validate_detection_config(self, config) -> None:
        """Validate detection configuration."""
        try:
            if hasattr(config, 'detection'):
                # Confidence threshold
                if hasattr(config.detection, 'confidence_threshold'):
                    conf = config.detection.confidence_threshold
                    if conf < 0.0 or conf > 1.0:
                        self._errors.append(ValidationError(
                            "detection.confidence_threshold",
                            f"Confidence threshold must be 0.0-1.0, got {conf}"
                        ))
                    elif conf < 0.3:
                        self._warnings.append(ValidationError(
                            "detection.confidence_threshold",
                            f"Very low confidence threshold ({conf}), may produce many false positives",
                            severity="warning"
                        ))

                # NMS threshold
                if hasattr(config.detection, 'nms_threshold'):
                    nms = config.detection.nms_threshold
                    if nms < 0.0 or nms > 1.0:
                        self._errors.append(ValidationError(
                            "detection.nms_threshold",
                            f"NMS threshold must be 0.0-1.0, got {nms}"
                        ))

        except AttributeError:
            # Detection config may be optional
            pass

    def _validate_calibration(self, config) -> None:
        """Validate calibration configuration."""
        try:
            if hasattr(config, 'calibration'):
                # Focal length
                if hasattr(config.calibration, 'focal_length'):
                    focal = config.calibration.focal_length
                    if focal <= 0:
                        self._errors.append(ValidationError(
                            "calibration.focal_length",
                            f"Focal length must be positive, got {focal}"
                        ))
                    elif focal < 100:
                        self._warnings.append(ValidationError(
                            "calibration.focal_length",
                            f"Very low focal length ({focal}mm), check calibration",
                            severity="warning"
                        ))

                # Baseline
                if hasattr(config.calibration, 'baseline'):
                    baseline = config.calibration.baseline
                    if baseline <= 0:
                        self._errors.append(ValidationError(
                            "calibration.baseline",
                            f"Baseline must be positive, got {baseline}"
                        ))

        except AttributeError:
            # Calibration config may be optional
            pass


__all__ = [
    "ValidationError",
    "ConfigValidator",
]
