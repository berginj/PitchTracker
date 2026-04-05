"""Camera adjustment controls for the calibration step."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.services.tooling import get_tooling_service
from capture import CameraDevice
from contracts.tooling import CalibrationRequest
from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)
from log_config.logger import get_logger
from ui.setup.steps.calibration_errors import build_calibration_error_payload
from ui.setup.steps.calibration_worker import CalibrationWorker
from ui.themes import (
    apply_standard_layout,
    ask_confirmation,
    build_notice,
    get_style_manager,
    polish_form_controls,
    show_choice_dialog,
    show_message_dialog,
    style_message_panel,
    style_preview_surface,
    style_progress_bar,
    style_status_label,
)

logger = get_logger(__name__)


class CalibrationStepCameraAdjustmentsMixin:
    def _toggle_flip(self, camera: str, checked: bool) -> None:
        """Toggle camera flip and restart cameras.

        Args:
            camera: "left" or "right"
            checked: True to flip 180°, False for normal orientation
        """
        import yaml

        # Update config file
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("camera", {})

        if camera == "left":
            data["camera"]["flip_left"] = checked
            # Clear rotation correction since alignment will be rechecked after flip
            data["camera"]["rotation_left"] = 0.0
        else:
            data["camera"]["flip_right"] = checked
            # Clear rotation correction since alignment will be rechecked after flip
            data["camera"]["rotation_right"] = 0.0

        # Also clear vertical offset since camera orientation changed
        data["camera"]["vertical_offset_px"] = 0

        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Show feedback message
        orientation = "flipped 180°" if checked else "normal"
        logger.info("{} camera set to {}; restarting cameras", camera.capitalize(), orientation)

        # Restart cameras if open to apply flip
        if self._left_camera is not None or self._right_camera is not None:
            # Stop preview
            self._preview_timer.stop()

            # Close cameras
            self._close_cameras()

            # Reopen with new flip setting after short delay
            QtCore.QTimer.singleShot(300, self._restart_cameras_after_flip)

    def _set_manual_rotation(self, camera: str, degrees: float) -> None:
        """Set manual rotation correction for a camera.

        Args:
            camera: "left" or "right"
            degrees: Rotation angle in degrees (positive = clockwise)
        """
        import yaml

        # Update config file
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("camera", {})

        if camera == "left":
            data["camera"]["rotation_left"] = float(degrees)
        else:
            data["camera"]["rotation_right"] = float(degrees)

        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Restart cameras if open to apply rotation
        if self._left_camera is not None or self._right_camera is not None:
            self._preview_timer.stop()
            self._close_cameras()
            QtCore.QTimer.singleShot(300, self._restart_cameras_after_flip)

    def _reset_all_corrections(self) -> None:
        """Reset all rotation and offset corrections to zero."""
        import yaml

        # Update config file
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("camera", {})

        # Reset all correction values
        data["camera"]["rotation_left"] = 0.0
        data["camera"]["rotation_right"] = 0.0
        data["camera"]["vertical_offset_px"] = 0

        # Clear alignment quality data
        if "alignment_quality" in data["camera"]:
            del data["camera"]["alignment_quality"]

        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Reset UI controls
        self._rotate_left_spin.setValue(0.0)
        self._rotate_right_spin.setValue(0.0)

        logger.info("Reset all manual camera rotation and offset corrections")

        # Restart cameras if open to apply reset
        if self._left_camera is not None or self._right_camera is not None:
            self._preview_timer.stop()
            self._close_cameras()
            QtCore.QTimer.singleShot(300, self._restart_cameras_after_flip)

    def _restart_cameras_after_flip(self) -> None:
        """Reopen cameras and restart preview after flip setting change."""
        try:
            self._open_cameras()

            # Restart preview if cameras opened successfully
            if self._left_camera and self._right_camera:
                self._preview_timer.start(33)  # ~30 FPS
                logger.info("Restarted cameras after flip or rotation change")
        except Exception:
            logger.exception("Failed to restart cameras after flip or rotation change")

    def _on_auto_detect_toggled(self, state: int) -> None:
        """Handle auto-detection checkbox toggle."""
        enabled = state == QtCore.Qt.CheckState.Checked.value

        if enabled:
            # Re-enable auto-detection
            self._pattern_locked = False
            logger.info("ChArUco pattern auto-detection enabled")
        else:
            # Disable auto-detection, use manual settings
            self._pattern_locked = True  # Lock prevents auto-detection
            logger.info(
                "ChArUco pattern auto-detection disabled; using manual settings {}x{} at {:.1f}mm",
                self._pattern_cols,
                self._pattern_rows,
                self._square_mm,
            )

    def _auto_swap_cameras(self) -> None:
        """Intelligently swap cameras based on ChArUco marker positions.

        Analyzes the horizontal position of markers in both camera views.
        If left camera sees markers more on the right side and right camera
        sees markers more on the left side, they should be swapped.
        """
        if not self._left_camera or not self._right_camera:
            show_message_dialog(
                self,
                "Cameras Not Ready",
                "Both cameras must be open to perform auto-swap.\n\n"
                "Please ensure both cameras are connected and showing previews.",
                tone="warning",
            )
            return

        try:
            # Get current frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            if not left_frame or not right_frame:
                show_message_dialog(
                    self,
                    "Frame Capture Failed",
                    "Could not capture frames from cameras.\n\n"
                    "Please ensure both cameras are working properly.",
                    tone="warning",
                )
                return

            # Detect markers in both images
            left_marker_pos = self._get_marker_horizontal_position(left_frame.image)
            right_marker_pos = self._get_marker_horizontal_position(right_frame.image)

            if left_marker_pos is None or right_marker_pos is None:
                show_message_dialog(
                    self,
                    "Board Not Detected",
                    "Could not detect ChArUco board in both cameras.\n\n"
                    "Please:\n"
                    "1. Hold board in view of BOTH cameras\n"
                    "2. Ensure board is well-lit and in focus\n"
                    "3. Wait for 'READY' status on both cameras\n"
                    "4. Try again",
                    tone="warning",
                )
                return

            # Determine if swap is needed
            # Left camera should see board on LEFT side of image (markers toward right)
            # Right camera should see board on RIGHT side of image (markers toward left)
            # If left camera's markers are on the right (> 0.5) and right camera's markers are on left (< 0.5), they're correct
            # If opposite, they need swapping

            should_swap = False
            explanation = ""
            confidence = 0.0

            # Calculate confidence based on how far markers are from center
            # Confidence increases as markers move away from center (0.5)
            left_deviation = abs(left_marker_pos - 0.5)
            right_deviation = abs(right_marker_pos - 0.5)
            avg_deviation = (left_deviation + right_deviation) / 2.0
            confidence = min(100, avg_deviation * 200)  # Scale to 0-100%

            if left_marker_pos > 0.6 and right_marker_pos < 0.4:
                # Correct orientation - left camera sees board toward right, right camera sees board toward left
                explanation = (
                    "Cameras are correctly positioned:\n\n"
                    f"Left camera sees board at {left_marker_pos:.1%} (toward right side) ✓\n"
                    f"Right camera sees board at {right_marker_pos:.1%} (toward left side) ✓\n\n"
                    f"Confidence: {confidence:.0f}%\n\n"
                    "No swap needed!"
                )
            elif left_marker_pos < 0.4 and right_marker_pos > 0.6:
                # Incorrect orientation - cameras need swapping
                should_swap = True
                explanation = (
                    "Cameras appear to be SWAPPED:\n\n"
                    f"Left camera sees board at {left_marker_pos:.1%} (toward left side) ✗\n"
                    f"Right camera sees board at {right_marker_pos:.1%} (toward right side) ✗\n\n"
                    f"Confidence: {confidence:.0f}%\n\n"
                    "Cameras will be swapped automatically."
                )
            else:
                # Ambiguous - board might be centered or detection unclear
                explanation = (
                    "Cannot determine camera orientation:\n\n"
                    f"Left camera sees board at {left_marker_pos:.1%}\n"
                    f"Right camera sees board at {right_marker_pos:.1%}\n\n"
                    f"Confidence: {confidence:.0f}% (too low for reliable detection)\n\n"
                    "Board appears centered or detection is unclear.\n\n"
                    "Tips:\n"
                    "• Move board more to one side\n"
                    "• Ensure board is clearly visible in both cameras\n"
                    "• Try manual swap if needed"
                )

            # Show results
            if should_swap:
                if ask_confirmation(
                    self,
                    "Swap Cameras?",
                    explanation + "\n\nSwap cameras now?",
                ):
                    self._swap_left_right()
                    show_message_dialog(
                        self,
                        "Cameras Swapped",
                        "Left and right cameras have been swapped.\n\n"
                        "The system will restart the cameras with the new assignment.",
                        tone="success",
                    )
            else:
                show_message_dialog(
                    self,
                    "Camera Orientation",
                    explanation,
                    tone="info",
                )

        except Exception as e:
            show_message_dialog(
                self,
                "Auto-Swap Error",
                f"Error during auto-swap detection:\n{str(e)}\n\n"
                "Please try manual swap if needed.",
                tone="error",
            )
