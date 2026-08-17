"""Lifecycle and setup state handlers for the calibration step."""

from __future__ import annotations

from ui.setup.steps.calibration_step_mixin_host import CalibrationStepMixinHost

import time
from pathlib import Path

from PySide6 import QtCore

from log_config.logger import get_logger
from ui.themes import (
    ask_confirmation,
    style_message_panel,
)

logger = get_logger(__name__)


class CalibrationStepLifecycleMixin(CalibrationStepMixinHost):
    def get_title(self) -> str:
        """Return step title."""
        return "Stereo Calibration"

    def validate(self) -> tuple[bool, str]:
        """Validate calibration is complete."""
        if self._calibration_result is None:
            return False, "Calibration not yet complete. Capture images and click 'Calibrate'."
        return True, ""

    def is_skippable(self) -> bool:
        """Calibration can be skipped if already exists."""
        calib_file = Path("calibration/stereo_calibration.npz")
        return calib_file.exists()

    def on_enter(self) -> None:
        """Called when step becomes active."""
        logger.debug(
            "Entering calibration step with left_serial={!r}, right_serial={!r}",
            self._left_serial,
            self._right_serial,
        )

        # Clear any old calibration images from temp directory
        self._clear_temp_images()

        # Reset capture state
        self._captures.clear()
        self._baseline_alignment = None  # Reset drift detection baseline
        self._alignment_history.clear()  # Reset alignment history for moving average
        self._warmup_attempts = 0  # Reset warmup counter
        self._capture_count_label.setText(f"Progress: 0/{self._min_captures} poses captured")
        self._set_capture_progress_state(0, ready=False)
        self._capture_progress_bar.setValue(0)
        self._calibrate_button.setEnabled(False)

        # Close any existing cameras first to release resources
        if self._left_camera or self._right_camera:
            self._close_cameras()
            # Give Windows time to release camera handles
            time.sleep(0.5)

        # Open cameras if serials are set
        if self._left_serial and self._right_serial:
            logger.debug("Both camera serials are available; opening calibration cameras")
            self._open_cameras()
        else:
            logger.warning(
                "Cannot open calibration cameras because serials are missing. left_serial={!r} (set={}), right_serial={!r} (set={})",
                self._left_serial,
                bool(self._left_serial),
                self._right_serial,
                bool(self._right_serial),
            )

        # Load previous alignment history
        self._load_alignment_history()

        # Auto-swap cameras based on history (if enabled)
        if self._auto_swap_on_startup and self._left_camera and self._right_camera:
            if self._check_camera_history():
                logger.info("Camera history indicates left/right assignments should be swapped")
                self._swap_left_right(save_to_history=False)  # Don't save yet, just swap
                logger.info("Applied startup camera swap from saved history")

        # Detect camera capabilities (Phase 3)
        if self._left_camera and not self._camera_detection_complete:
            logger.debug("Scheduling camera capability detection after preview warmup")
            # Run in background to avoid blocking UI
            QtCore.QTimer.singleShot(1000, self._detect_camera_capabilities)  # Delay 1s for camera warmup

        # Start preview timer
        if self._left_camera and self._right_camera:
            logger.debug("Starting calibration preview timer")
            self._preview_timer.start(33)  # ~30 FPS
        else:
            logger.warning(
                "Calibration preview timer not started because cameras are unavailable. left_camera={!r}, right_camera={!r}",
                self._left_camera,
                self._right_camera,
            )

    def on_exit(self) -> None:
        """Called when leaving step."""
        # Stop preview timer
        self._preview_timer.stop()

        # Close cameras
        self._close_cameras()

    def _on_mode_changed(self) -> None:
        """Handle calibration mode radio button change."""
        if self._quick_radio.isChecked():
            self._calibration_mode = "QUICK"
            self._min_captures = 5
            self._instruction_label.setText(
                "<b style='font-size: 14pt;'>📷 Capture 3-5 ChArUco Board Poses (Quick Mode)</b>"
            )
            self._capture_progress_bar.setMaximum(5)
            self._instruction_label.setText("Capture 3-5 ChArUco Board Poses (Quick Mode)")
            style_message_panel(self._instruction_label, "info")
        else:
            self._calibration_mode = "FULL"
            self._min_captures = 10
            self._instruction_label.setText("<b style='font-size: 14pt;'>📷 Capture 10+ ChArUco Board Poses</b>")
            self._capture_progress_bar.setMaximum(10)
            self._instruction_label.setText("Capture 10+ ChArUco Board Poses")
            style_message_panel(self._instruction_label, "info")

        # Update progress label
        count = len(self._captures)
        self._capture_count_label.setText(f"Progress: {count}/{self._min_captures} poses captured")
        self._set_capture_progress_state(count, ready=count >= self._min_captures)

        logger.debug("Calibration mode changed to {}", self._calibration_mode)

    def _detect_camera_capabilities(self) -> None:
        """Detect camera capabilities (type, autofocus, stability)."""
        if self._camera_detection_complete or not self._left_camera:
            return

        logger.debug("Detecting camera capabilities")
        self._camera_type_label.setText("Detecting camera type...")

        try:
            from calib.camera_capabilities import CameraCapabilityDetector

            detector = CameraCapabilityDetector()

            # Detect capabilities for left camera (representative of both)
            self._camera_capabilities = detector.detect_capabilities(
                self._left_camera,
                num_test_frames=20,  # Reduced for faster detection
                test_duration_s=3.0,  # Reduced for faster detection
            )

            self._camera_detection_complete = True
            self._update_camera_type_display()

            logger.info(
                "Camera capability detection complete: type={}, autofocus={}, stability={:.1f}/100",
                self._camera_capabilities.camera_type,
                self._camera_capabilities.has_autofocus,
                self._camera_capabilities.focal_stability_score,
            )

        except Exception as e:
            logger.warning("Camera capability detection failed: {}", e)
            self._camera_type_label.setText("Detection failed")
            self._camera_stability_label.setText("See console for details")

    def _update_camera_type_display(self) -> None:
        """Update UI with detected camera capabilities."""
        if not self._camera_capabilities:
            return

        caps = self._camera_capabilities

        # Update camera type label with emoji
        if caps.camera_type == "industrial":
            type_emoji = "✓"
            type_text = f"{type_emoji} Industrial (Fixed Focus)"
        elif caps.camera_type == "webcam":
            type_emoji = "⚠️"
            type_text = f"{type_emoji} Webcam (Autofocus)"
        else:
            type_emoji = "?"
            type_text = f"{type_emoji} Unknown"

        self._camera_type_label.setText(type_text)
        self._set_camera_type_state(
            "Industrial (Fixed Focus)"
            if caps.camera_type == "industrial"
            else ("Webcam (Autofocus)" if caps.camera_type == "webcam" else "Unknown Camera Type"),
            "success" if caps.camera_type == "industrial" else ("warning" if caps.camera_type == "webcam" else "info"),
        )

        # Update stability score
        score = caps.focal_stability_score
        self._camera_stability_label.setText(f"Stability: {score:.0f}/100")
        self._set_camera_stability_state(
            f"Stability: {score:.0f}/100",
            "success" if score >= 90 else ("warning" if score >= 70 else "error"),
        )

        # Show webcam warning if detected
        if caps.camera_type == "webcam" or caps.has_autofocus:
            warning_text = (
                "⚠️ WEBCAM DETECTED: Autofocus cameras may reduce accuracy\n"
                "Recommendation: Disable autofocus in camera settings or use manual focus cameras\n"
            )
            if caps.recommendations:
                # Show first 2 recommendations
                warning_text += "\n" + "\n".join(f"• {r}" for r in caps.recommendations[:2])

            self._set_webcam_warning(warning_text)

            # Suggest quick mode for webcams
            if self._calibration_mode == "FULL" and ask_confirmation(
                self,
                "Quick Calibration Recommended",
                "Webcam detected with autofocus.\n\n"
                "Quick calibration mode is recommended for cameras with autofocus "
                "as it's less sensitive to focal drift.\n\n"
                "Switch to Quick mode?",
                tone="warning",
            ):
                self._quick_radio.setChecked(True)
        else:
            self._set_webcam_warning(None)

    def set_camera_serials(self, left_serial: str, right_serial: str) -> None:
        """Set camera serials from Step 1."""
        logger.debug(
            "Received camera serials for calibration step: left_serial={!r}, right_serial={!r}",
            left_serial,
            right_serial,
        )
        self._left_serial = left_serial
        self._right_serial = right_serial
        logger.debug("Stored calibration camera serials")

    def _on_pattern_changed(self, value: int) -> None:
        """Handle pattern size change."""
        self._pattern_cols = self._pattern_cols_spin.value()
        self._pattern_rows = self._pattern_rows_spin.value()
        self._update_pattern_info()
        self._user_changed_pattern = True
        self._pattern_locked = not self._auto_detect_pattern_checkbox.isChecked()
        logger.debug("User changed ChArUco pattern to {}x{}", self._pattern_cols, self._pattern_rows)

    def _on_square_size_changed(self, value: float) -> None:
        """Handle square size change."""
        self._square_mm = value
        self._update_pattern_info()
        self._user_changed_pattern = True
        self._pattern_locked = not self._auto_detect_pattern_checkbox.isChecked()
        logger.debug("User changed ChArUco square size to {:.1f}mm", self._square_mm)

    def _update_pattern_info(self) -> None:
        """Update the pattern info label."""
        auto_enabled = self._auto_detect_pattern_checkbox.isChecked()
        if auto_enabled and self._pattern_locked and self._cached_dict_name:
            dict_display = self._cached_dict_name.replace("DICT_", "").replace("_", " ")
            self._pattern_info_label.setText(f"Detected: {self._pattern_cols}×{self._pattern_rows} ({dict_display})")
            self._set_pattern_info_state(self._pattern_info_label.text(), "success")
        elif auto_enabled and self._cached_dict_name:
            dict_display = self._cached_dict_name.replace("DICT_", "").replace("_", " ")
            self._pattern_info_label.setText(f"Scanning... ({dict_display})")
            self._set_pattern_info_state(self._pattern_info_label.text(), "warning")
        elif auto_enabled:
            self._pattern_info_label.setText("Auto-detection enabled; scanning...")
            self._set_pattern_info_state(self._pattern_info_label.text(), "warning")
        else:
            self._pattern_info_label.setText(
                f"Manual board: {self._pattern_cols}x{self._pattern_rows}, {self._square_mm:.1f} mm"
            )
            self._set_pattern_info_state(self._pattern_info_label.text(), "info")
