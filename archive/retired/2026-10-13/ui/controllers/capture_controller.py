"""Camera capture lifecycle management controller.

Extracted from MainWindow to reduce god class complexity.
Manages camera capture start/stop and pre-capture validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

from PySide6 import QtWidgets

from app.services.rig_profile import CRITICAL, WARN, RigProfileService
from configs.validator import validate_config_file as validate_yaml_config_file
from exceptions import ConfigValidationError
from log_config.logger import get_logger
from ui.themes import ask_confirmation, show_message_dialog

if TYPE_CHECKING:
    from configs.settings import AppConfig

logger = get_logger(__name__)


def validate_config_file(config_path: str) -> None:
    """Validate config file using ConfigValidator.

    Args:
        config_path: Path to config file

    Raises:
        ConfigValidationError: If validation fails
    """
    validate_yaml_config_file(config_path)


class CaptureController:
    """Manages camera capture lifecycle.

    Responsibilities:
    - Starting and stopping camera capture
    - Pre-capture validation checks
    - Timer management for capture loop
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        status_label: QtWidgets.QLabel,
        get_config: Callable[[], "AppConfig"],
        get_config_path: Callable[[], Path],
        get_left_serial: Callable[[], Optional[str]],
        get_right_serial: Callable[[], Optional[str]],
        get_roi_path: Callable[[], Path],
        get_lane_path: Callable[[], Path],
        start_timer: Callable[[int], None],
        stop_timer: Callable[[], None],
        stop_replay: Callable[[], None],
        start_capture_service: Callable[["AppConfig", str, str, Path], None],
        stop_capture_service: Callable[[], None],
    ):
        """Initialize capture controller.

        Args:
            parent: Parent widget for dialogs
            status_label: Label for status messages
            get_config: Callback to get current config
            get_config_path: Callback to get config file path
            get_left_serial: Callback to get left camera serial
            get_right_serial: Callback to get right camera serial
            get_roi_path: Callback to get ROI file path
            get_lane_path: Callback to get lane ROI file path
            start_timer: Callback to start refresh timer (takes ms interval)
            stop_timer: Callback to stop refresh timer
            stop_replay: Callback to stop video replay
            start_capture_service: Callback to start capture in service
            stop_capture_service: Callback to stop capture in service
        """
        self._parent = parent
        self._status_label = status_label
        self._get_config = get_config
        self._get_config_path = get_config_path
        self._get_left_serial = get_left_serial
        self._get_right_serial = get_right_serial
        self._get_roi_path = get_roi_path
        self._get_lane_path = get_lane_path
        self._start_timer = start_timer
        self._stop_timer = stop_timer
        self._stop_replay = stop_replay
        self._start_capture_service = start_capture_service
        self._stop_capture_service = stop_capture_service

        logger.debug("CaptureController initialized")

    def start_capture(self) -> bool:
        """Start camera capture.

        Returns:
            True if capture started successfully, False otherwise
        """
        left = self._get_left_serial()
        right = self._get_right_serial()

        if not left or not right:
            self._status_label.setText("Enter both serials.")
            logger.warning("Capture start failed - missing serials")
            return False

        if not self.pre_capture_check():
            return False

        self._stop_replay()

        config = self._get_config()
        config_path = self._get_config_path()
        self._start_capture_service(config, left, right, config_path)
        self._status_label.setText("Capturing.")

        refresh_ms = int(1000 / max(config.ui.refresh_hz, 1))
        self._start_timer(refresh_ms)

        logger.info(f"Capture started: left={left}, right={right}")
        return True

    def stop_capture(self) -> None:
        """Stop camera capture."""
        self._stop_timer()
        self._stop_capture_service()
        self._status_label.setText("Stopped.")
        logger.info("Capture stopped")

    def restart_capture(self) -> None:
        """Restart camera capture."""
        self.stop_capture()
        self.start_capture()
        logger.info("Capture restarted")

    def pre_capture_check(self) -> bool:
        """Run pre-capture validation checks.

        Returns:
            True if all checks pass, False otherwise
        """
        errors: list[str] = []
        warnings: list[str] = []

        config = self._get_config()
        config_path = self._get_config_path()
        roi_path = self._get_roi_path()
        lane_path = self._get_lane_path()
        left_serial = self._get_left_serial()
        right_serial = self._get_right_serial()

        # Validate config file
        try:
            validate_config_file(str(config_path))
        except ConfigValidationError as exc:
            errors.append(str(exc))
            for detail in exc.validation_errors:
                errors.append(f"- {detail}")

        # Check ML detector model
        if config.detector.type == "ml":
            model_path = config.detector.model_path
            if not model_path:
                errors.append("ML detector enabled but model_path is empty.")
            else:
                resolved = Path(model_path)
                if not resolved.exists():
                    errors.append(f"ML model not found at {resolved}.")

        # Check output directory
        output_dir = Path(config.recording.output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"Output dir not writable: {output_dir} ({exc})")
        else:
            if not os.access(output_dir, os.W_OK):
                errors.append(f"Output dir not writable: {output_dir}")

        # Check ROI files
        if not roi_path.exists():
            warnings.append(f"ROI file {roi_path} not found; lane/plate gating will be disabled.")
        if not lane_path.exists():
            warnings.append(f"Lane ROI overrides not found at {lane_path}; " "using shared lane ROI for both cameras.")

        profile_service = RigProfileService(config_path=config_path)
        active_profile = profile_service.load_active()
        if active_profile is not None:
            validation = profile_service.validate_for_runtime(
                active_profile,
                config=config,
                left_serial=left_serial,
                right_serial=right_serial,
            )
            if validation.state == CRITICAL:
                errors.extend(validation.issues)
            elif validation.state == WARN:
                warnings.extend(validation.warnings)

        # Show errors
        if errors:
            show_message_dialog(
                self._parent,
                "Pre-Capture Check Failed",
                "Fix the following before capturing:\n" + "\n".join(errors),
                tone="error",
            )
            logger.warning(f"Pre-capture check failed: {errors}")
            return False

        # Show warnings
        if warnings:
            if not ask_confirmation(
                self._parent,
                "Pre-Capture Warnings",
                "Continue with the following warnings?\n" + "\n".join(warnings),
                tone="warning",
            ):
                logger.info("User cancelled capture due to warnings")
                return False

        logger.debug("Pre-capture check passed")
        return True
