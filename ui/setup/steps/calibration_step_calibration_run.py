"""Calibration execution handlers for the calibration step."""

from __future__ import annotations


from PySide6 import QtCore

from log_config.logger import get_logger
from ui.setup.steps.calibration_worker import CalibrationWorker
from ui.themes import (
    show_message_dialog,
)

logger = get_logger(__name__)


class CalibrationStepCalibrationRunMixin:
    def _run_calibration(self) -> None:
        """Run stereo calibration on captured images."""
        if len(self._captures) < self._min_captures:
            show_message_dialog(
                self,
                "Insufficient Captures",
                f"Need at least {self._min_captures} captures. Currently have {len(self._captures)}.",
                tone="warning",
            )
            return

        # Show progress bar
        self._progress_bar.show()
        self._results_text.hide()
        self._calibrate_button.setEnabled(False)
        self._capture_button.setEnabled(False)

        # Get image paths
        left_paths = sorted(self._temp_dir.glob("left_*.png"))
        right_paths = sorted(self._temp_dir.glob("right_*.png"))

        # Create and start worker thread
        pattern = f"{self._pattern_cols}x{self._pattern_rows}"
        quick_mode = (self._calibration_mode == "QUICK")

        logger.info("Running stereo calibration in {} mode", self._calibration_mode)

        self._calibration_worker = CalibrationWorker(
            left_paths,
            right_paths,
            pattern,
            self._square_mm,
            self._config_path,
            quick_mode=quick_mode,
        )
        self._calibration_worker.finished.connect(self._on_calibration_complete)
        self._calibration_worker.error.connect(self._on_calibration_error)
        self._calibration_worker.start()

    def _on_calibration_complete(self, result: dict) -> None:
        """Handle successful calibration with quality metrics."""
        self._calibration_result = result

        # Hide progress bar
        self._progress_bar.hide()

        # Extract quality metrics (with new field names from improved calibrate_and_write)
        rating = result.get('quality_rating', 'UNKNOWN')
        emoji = result.get('quality_emoji', '✅')
        description = result.get('quality_description', 'Calibration complete')
        rms_error = result.get('rms_error_px', 0.0)
        num_images = result.get('num_images_used', result.get('num_images', 0))
        total_input = result.get('total_input_images', num_images)
        rejected = total_input - num_images
        recommendations = result.get('recommendations', [])

        # Build results text with quality metrics
        mode = result.get('calibration_mode', 'FULL')
        results_text = (
            f"{emoji} Calibration {rating}! (Mode: {mode})\n\n"
            f"Baseline: {result['baseline_ft']:.3f} ft\n"
            f"Focal Length: {result['focal_length_px']:.1f} px\n"
            f"Principal Point: ({result['cx']:.1f}, {result['cy']:.1f})\n\n"
            f"Quality Metrics:\n"
            f"  Reprojection Error: {rms_error:.3f} px\n"
            f"  Images Used: {num_images}/{total_input}"
        )

        if rejected > 0:
            results_text += f"\n  Rejected: {rejected} pairs (corner detection failed)"

        results_text += f"\n\n{description}\n"

        if recommendations:
            results_text += "\nRecommendations:\n"
            for rec in recommendations:
                results_text += f"  • {rec}\n"

        results_text += f"\nCalibration saved to {self._config_path}"

        self._results_text.setText(results_text)
        self._set_results_state(results_text, self._tone_for_calibration_rating(rating))
        self._results_text.show()

        # Update baseline spinner with calibrated value
        calibrated_baseline = result['baseline_ft']
        self._baseline_spin.blockSignals(True)  # Don't trigger valueChanged
        self._baseline_spin.setValue(calibrated_baseline)
        self._baseline_spin.blockSignals(False)

        # Update baseline status to show it's now calibrated (blue)
        baseline_inches = calibrated_baseline * 12
        self._baseline_inches_label.setText(f"({baseline_inches:.1f} in) 📐 Calibrated")
        self._set_baseline_state(
            f"{baseline_inches:.1f} in · Calibrated",
            "info",
            "This value was calculated by stereo calibration (more accurate than manual measurement)",
        )

        # Re-enable buttons
        self._capture_button.setEnabled(True)
        self._calibrate_button.setEnabled(True)

        # Show appropriate message dialog based on quality
        if rating == 'POOR':
            show_message_dialog(
                self,
                "Poor Calibration Quality",
                f"Calibration quality is poor (RMS error: {rms_error:.2f} px).\n\n"
                f"We strongly recommend recalibrating:\n\n"
                + "\n".join(recommendations),
                tone="warning",
            )
        elif rating in ['EXCELLENT', 'GOOD']:
            show_message_dialog(
                self,
                "Calibration Complete",
                f"Stereo calibration completed with {rating} quality!\n\n"
                f"Reprojection error: {rms_error:.3f} px\n\n"
                "You can now proceed to the next step.",
                tone="success",
            )
        else:  # ACCEPTABLE
            show_message_dialog(
                self,
                "Calibration Complete",
                f"Stereo calibration completed with acceptable quality.\n\n"
                f"Reprojection error: {rms_error:.3f} px\n\n"
                "You can proceed, but consider recalibrating with more images for better accuracy.",
                tone="info",
            )

    def _on_calibration_error(self, error: dict | str) -> None:
        """Handle calibration error."""
        if isinstance(error, dict):
            error_title = str(error.get("title", "Calibration Error"))
            error_tone = str(error.get("tone", "error"))
            error_msg = str(error.get("message", "Calibration failed"))
        else:
            error_title = "Calibration Error"
            error_tone = "error"
            error_msg = str(error)

        # Hide progress bar
        self._progress_bar.hide()

        # Show error
        self._set_results_state(f"{error_title}:\n{error_msg}", error_tone)
        self._results_text.show()

        # Re-enable buttons
        self._capture_button.setEnabled(True)
        self._calibrate_button.setEnabled(True)

        show_message_dialog(
            self,
            error_title,
            error_msg,
            tone=error_tone,
        )

    # ========================================================================
    # Automatic Alignment Check
    # ========================================================================

    def _wait_for_camera_warmup(self) -> None:
        """Wait for cameras to warm up and stabilize before alignment check.

        Monitors frame variance to detect when auto-exposure, auto-focus,
        and auto-white-balance have settled.
        """
        if not self._left_camera or not self._right_camera:
            return

        try:
            from analysis.camera_alignment import check_camera_warmup

            # Update alignment widget
            self._alignment_status_label.setText("⏳ Waiting for cameras to stabilize...")
            self._set_alignment_state("Waiting for cameras to stabilize...", "warning")

            # Check both cameras
            left_stable, left_variance = check_camera_warmup(self._left_camera, num_frames=15)
            right_stable, right_variance = check_camera_warmup(self._right_camera, num_frames=15)

            both_stable = left_stable and right_stable

            if both_stable:
                # Cameras are stable - proceed with alignment check
                self._alignment_status_label.setText(
                    f"✓ Cameras stable (variance: L={left_variance:.3f}, R={right_variance:.3f})"
                )
                self._set_alignment_state(
                    f"Cameras stable (variance: L={left_variance:.3f}, R={right_variance:.3f})",
                    "success",
                )
                # Schedule alignment check
                QtCore.QTimer.singleShot(500, self._run_automatic_alignment_check)
            else:
                # Cameras still warming up - wait longer
                unstable_cameras = []
                if not left_stable:
                    unstable_cameras.append(f"Left ({left_variance:.3f})")
                if not right_stable:
                    unstable_cameras.append(f"Right ({right_variance:.3f})")

                self._alignment_status_label.setText(
                    f"⏳ Cameras still warming up: {', '.join(unstable_cameras)}\n"
                    f"Waiting 2 more seconds..."
                )

                self._set_alignment_state(
                    f"Cameras still warming up: {', '.join(unstable_cameras)}\nWaiting 2 more seconds...",
                    "warning",
                )
                # Wait another 2 seconds and check again (max 3 attempts)
                if not hasattr(self, '_warmup_attempts'):
                    self._warmup_attempts = 0

                self._warmup_attempts += 1

                if self._warmup_attempts < 3:
                    # Try again
                    QtCore.QTimer.singleShot(2000, self._wait_for_camera_warmup)
                else:
                    # Give up waiting, proceed anyway
                    self._alignment_status_label.setText(
                        "⚠️ Cameras may not be fully stable, but proceeding with check..."
                    )
                    self._set_alignment_state(
                        "Cameras may not be fully stable, but proceeding with check...",
                        "warning",
                    )
                    self._warmup_attempts = 0
                    QtCore.QTimer.singleShot(500, self._run_automatic_alignment_check)

        except Exception as e:
            # If warmup check fails, just proceed with alignment check
            logger.warning("Camera warmup check failed; proceeding with alignment anyway: {}", e)
            self._warmup_attempts = 0
            QtCore.QTimer.singleShot(500, self._run_automatic_alignment_check)
