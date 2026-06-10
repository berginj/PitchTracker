"""Alignment analysis routines for the calibration step."""

from __future__ import annotations


import numpy as np
from PySide6 import QtWidgets

from log_config.logger import get_logger
from ui.themes import (
    show_choice_dialog,
    show_message_dialog,
)

logger = get_logger(__name__)


class CalibrationStepAlignmentMixin:
    def _check_alignment_drift(self, left_img: np.ndarray, right_img: np.ndarray) -> bool:
        """Check if camera alignment has drifted since first capture.

        Uses moving average of recent alignments to reduce false positives from single-frame anomalies.

        Args:
            left_img: Current left camera image
            right_img: Current right camera image

        Returns:
            True if user chose to abort this capture (drift too large), False to continue
        """
        if self._baseline_alignment is None or len(self._alignment_history) == 0:
            return False  # No baseline, can't check drift

        try:
            from analysis.camera_alignment import analyze_alignment

            # Analyze current alignment
            current = analyze_alignment(left_img, right_img)

            # Calculate moving average of recent alignments (last 3-5 captures)
            # This reduces false positives from single-capture anomalies
            window_size = min(5, len(self._alignment_history))
            recent_alignments = self._alignment_history[-window_size:]

            # Calculate average metrics from recent captures
            avg_convergence = sum(a.convergence_std_px for a in recent_alignments) / len(recent_alignments)
            avg_vertical = sum(a.vertical_mean_px for a in recent_alignments) / len(recent_alignments)
            avg_rotation = sum(a.rotation_deg for a in recent_alignments) / len(recent_alignments)
            avg_focal = sum(a.scale_difference_percent for a in recent_alignments) / len(recent_alignments)

            # Calculate drift compared to moving average (more robust than single baseline)
            toin_drift = abs(current.convergence_std_px - avg_convergence)
            vertical_drift = abs(current.vertical_mean_px - avg_vertical)
            rotation_drift = abs(current.rotation_deg - avg_rotation)
            focal_drift = abs(current.scale_difference_percent - avg_focal)

            # Dynamic threshold adjustment based on alignment history variance
            # More stable mounts get tighter thresholds; less stable mounts get more tolerance
            if len(recent_alignments) >= 3:
                # Calculate standard deviation of recent measurements
                import math

                toin_std = math.sqrt(
                    sum((a.convergence_std_px - avg_convergence) ** 2 for a in recent_alignments)
                    / len(recent_alignments)
                )
                vertical_std = math.sqrt(
                    sum((a.vertical_mean_px - avg_vertical) ** 2 for a in recent_alignments) / len(recent_alignments)
                )
                rotation_std = math.sqrt(
                    sum((a.rotation_deg - avg_rotation) ** 2 for a in recent_alignments) / len(recent_alignments)
                )
                focal_std = math.sqrt(
                    sum((a.scale_difference_percent - avg_focal) ** 2 for a in recent_alignments)
                    / len(recent_alignments)
                )

                # Base thresholds for FIXED MOUNTS
                base_toin_threshold = 15.0
                base_vertical_threshold = 10.0
                base_rotation_threshold = 5.0
                base_focal_threshold = 5.0

                # Adjust thresholds: if variance is high, be more tolerant (up to 1.5x)
                # if variance is very low, be stricter (down to 0.7x)
                toin_threshold = base_toin_threshold * max(0.7, min(1.5, 1.0 + toin_std / 10.0))
                vertical_threshold = base_vertical_threshold * max(0.7, min(1.5, 1.0 + vertical_std / 5.0))
                rotation_threshold = base_rotation_threshold * max(0.7, min(1.5, 1.0 + rotation_std / 2.0))
                focal_threshold = base_focal_threshold * max(0.7, min(1.5, 1.0 + focal_std / 2.0))
            else:
                # Not enough history for dynamic adjustment, use fixed thresholds
                toin_threshold = 15.0
                vertical_threshold = 10.0
                rotation_threshold = 5.0
                focal_threshold = 5.0

            # Determine if drift is significant using dynamic thresholds
            significant_drift = (
                toin_drift > toin_threshold
                or vertical_drift > vertical_threshold
                or rotation_drift > rotation_threshold
                or focal_drift > focal_threshold
            )

            if not significant_drift:
                return False  # No significant drift, continue

            # Build drift warning message with dynamic thresholds
            drift_details = []
            if toin_drift > toin_threshold:
                drift_details.append(
                    f"  • Toe-in: {avg_convergence:.1f}px (avg) → "
                    f"{current.convergence_std_px:.1f}px (Δ {toin_drift:.1f}px, threshold: {toin_threshold:.1f}px)"
                )
            if vertical_drift > vertical_threshold:
                drift_details.append(
                    f"  • Vertical: {avg_vertical:.1f}px (avg) → "
                    f"{current.vertical_mean_px:.1f}px (Δ {vertical_drift:.1f}px, threshold: {vertical_threshold:.1f}px)"
                )
            if rotation_drift > rotation_threshold:
                drift_details.append(
                    f"  • Rotation: {avg_rotation:.1f}° (avg) → "
                    f"{current.rotation_deg:.1f}° (Δ {rotation_drift:.1f}°, threshold: {rotation_threshold:.1f}°)"
                )
            if focal_drift > focal_threshold:
                drift_details.append(
                    f"  • Focal Length: {avg_focal:.1f}% (avg) → "
                    f"{current.scale_difference_percent:.1f}% (Δ {focal_drift:.1f}%, threshold: {focal_threshold:.1f}%)"
                )

            warning_msg = (
                f"⚠️ Camera alignment has drifted from recent captures!\n\n"
                f"Changes detected (compared to last {window_size} captures):\n" + "\n".join(drift_details) + "\n\n"
                "This can invalidate calibration. Recommendations:\n\n"
                "• Click 'Restart' to clear captures and start over (recommended)\n"
                "• Click 'Continue' to capture anyway (may reduce calibration quality)\n"
                "• Click 'Cancel' to skip this capture and reposition cameras"
            )

            choice = show_choice_dialog(
                self,
                "Alignment Drift Detected",
                warning_msg,
                tone="warning",
                choices=(
                    ("restart", "Restart Calibration", "danger", QtWidgets.QMessageBox.ButtonRole.DestructiveRole),
                    ("continue", "Continue Anyway", "primary", QtWidgets.QMessageBox.ButtonRole.AcceptRole),
                    ("cancel", "Cancel Capture", "ghost", QtWidgets.QMessageBox.ButtonRole.RejectRole),
                ),
                default_choice="restart",
            )

            if choice == "restart":
                # Restart calibration - clear all captures and alignment history
                self._captures.clear()
                self._baseline_alignment = None
                self._alignment_history.clear()
                self._capture_count_label.setText(f"Progress: 0/{self._min_captures} poses captured")
                self._set_capture_progress_state(0, ready=False)
                self._capture_progress_bar.setValue(0)
                self._calibrate_button.setEnabled(False)

                # Clear temp directory
                self._clear_temp_images()

                show_message_dialog(
                    self,
                    "Calibration Restarted",
                    "All captures cleared. Please start capturing again with stable camera positions.",
                    tone="success",
                )
                return True  # Abort this capture

            elif choice == "cancel":
                # Just skip this capture
                return True  # Abort this capture

            else:  # continue
                # User chose to continue despite drift
                return False  # Allow capture to proceed

        except Exception as e:
            # Don't block captures if drift detection fails
            logger.warning("Alignment drift check failed; allowing capture to proceed: {}", e)
            return False

    def _run_automatic_alignment_check(self) -> None:
        """Automatically run camera alignment check in background.

        This runs 3 seconds after cameras open to check alignment quality.
        Uses multi-frame averaging for robust measurements.
        Results are displayed in the alignment status widget.
        Software corrections are applied automatically if needed.
        """
        if not self._left_camera or not self._right_camera:
            return

        try:
            # Update UI to show checking
            self._alignment_status_label.setText("⏳ Analyzing alignment (averaging 10 frames)...")
            self._set_alignment_state("Analyzing alignment (averaging 10 frames)...", "info")

            # Run alignment analysis with multi-frame averaging
            from analysis.camera_alignment import analyze_alignment_averaged, apply_corrections, save_alignment_frames

            results = analyze_alignment_averaged(self._left_camera, self._right_camera, num_frames=10, interval_ms=100)

            # Store results for detail view
            self._alignment_results = results

            # Save frames for debugging
            try:
                left_frame = self._left_camera.read_frame(timeout_ms=1000)
                right_frame = self._right_camera.read_frame(timeout_ms=1000)
                save_alignment_frames(left_frame.image, right_frame.image, results)
            except Exception:
                pass  # Don't fail if saving frames fails

            # Update UI based on results
            self._display_alignment_results(results)

            # Automatically apply software corrections if enabled AND needed
            if self._auto_correct_checkbox.isChecked():
                if results.rotation_correction_needed or abs(results.vertical_offset_px) > 5:
                    apply_corrections(self._config_path, results)

                    # Restart cameras to apply rotation correction
                    if results.rotation_correction_needed:
                        self._restart_cameras_after_correction()
            else:
                # Show message that auto-corrections are disabled
                if results.rotation_correction_needed or abs(results.vertical_offset_px) > 5:
                    logger.info("Alignment corrections were detected but auto-correct is disabled")

            # Enable buttons
            self._recheck_alignment_btn.show()
            self._quick_check_btn.show()
            self._alignment_details_btn.show()
            self._show_features_btn.show()
            self._export_report_btn.show()
            self._save_preset_btn.show()
            self._load_preset_btn.show()
            self._compare_preset_btn.show()

            # Quality gate: Disable calibrate button if alignment is critical
            if not results.can_calibrate():
                self._calibrate_button.setEnabled(False)
                self._calibrate_button.setToolTip(
                    "Calibration blocked - camera alignment is too poor.\n"
                    "Please adjust cameras to be parallel (fix toe-in)."
                )

        except Exception as e:
            # Show error in alignment widget
            self._alignment_status_label.setText(f"❌ Alignment check failed: {str(e)}")
            self._set_alignment_state(f"Alignment check failed: {str(e)}", "error")
            self._alignment_results = None

    def _run_quick_alignment_check(self) -> None:
        """Run quick alignment check (single frame, no averaging).

        Faster than full check but less robust. Good for rapid iteration
        when making small adjustments.
        """
        if not self._left_camera or not self._right_camera:
            return

        try:
            # Update UI to show checking
            self._alignment_status_label.setText("⚡ Quick check (1 frame)...")
            self._set_alignment_state("Quick check (1 frame)...", "info")

            # Run single-frame alignment analysis
            from analysis.camera_alignment import analyze_alignment, apply_corrections

            # Capture frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            # Analyze (single frame)
            results = analyze_alignment(left_frame.image, right_frame.image)

            # Store results for detail view
            self._alignment_results = results

            # Update UI based on results (will show quick check badge)
            self._display_alignment_results(results, quick_check=True)

            # Automatically apply software corrections if enabled AND needed
            if self._auto_correct_checkbox.isChecked():
                if results.rotation_correction_needed or abs(results.vertical_offset_px) > 5:
                    apply_corrections(self._config_path, results)

                    # Restart cameras to apply rotation correction
                    if results.rotation_correction_needed:
                        self._restart_cameras_after_correction()
            else:
                # Show message that auto-corrections are disabled
                if results.rotation_correction_needed or abs(results.vertical_offset_px) > 5:
                    logger.info("Alignment corrections were detected but auto-correct is disabled")

            # Enable buttons
            self._recheck_alignment_btn.show()
            self._quick_check_btn.show()
            self._alignment_details_btn.show()
            self._show_features_btn.show()
            self._export_report_btn.show()
            self._save_preset_btn.show()
            self._load_preset_btn.show()
            self._compare_preset_btn.show()

            # Quality gate: Disable calibrate button if alignment is critical
            if not results.can_calibrate():
                self._calibrate_button.setEnabled(False)
                self._calibrate_button.setToolTip(
                    "Calibration blocked - camera alignment is too poor.\n"
                    "Please adjust cameras to be parallel (fix toe-in)."
                )

        except Exception as e:
            # Show error in alignment widget
            self._alignment_status_label.setText(f"❌ Quick check failed: {str(e)}")
            self._set_alignment_state(f"Quick check failed: {str(e)}", "error")
            self._alignment_results = None

    def _display_alignment_results(self, results, quick_check: bool = False) -> None:
        """Display alignment results in the status widget.

        Args:
            results: AlignmentResults object from analysis
        """
        # Choose color and icon based on quality
        if results.quality == "CRITICAL":
            bg_color = self._theme.accent_error_dim
            border_color = self._theme.accent_error
            text_color = self._theme.accent_error
            icon = "❌"
        elif results.quality == "POOR":
            bg_color = self._theme.accent_warning_dim
            border_color = self._theme.accent_warning
            text_color = self._theme.accent_warning
            icon = "⚠️"
        elif results.quality == "ACCEPTABLE":
            bg_color = self._theme.accent_warning_dim
            border_color = self._theme.accent_warning
            text_color = self._theme.accent_warning
            icon = "🟡"
        elif results.quality == "GOOD":
            bg_color = self._theme.accent_success_dim
            border_color = self._theme.accent_success
            text_color = self._theme.accent_success
            icon = "✓"
        else:  # EXCELLENT
            bg_color = self._theme.accent_success_dim
            border_color = self._theme.accent_success
            text_color = self._theme.accent_success
            icon = "✅"

        # Build status message
        status_html = f"<b>{icon} {results.status_message}</b>"

        # Add badge if quick check
        if quick_check:
            status_html += f" <span style='background-color: {self._theme.accent_warning}; color: black; padding: 2px 6px; border-radius: 3px; font-size: 8pt;'>⚡ QUICK CHECK</span>"
            status_html += (
                "<br><i style='font-size: 9pt;'>Single-frame analysis - run Full Check for averaged results</i>"
            )

        # Add corrections applied
        if results.corrections_applied:
            status_html += "<br><br><b>Corrections Applied:</b><br>"
            for correction in results.corrections_applied:
                status_html += f"  • {correction}<br>"

        # Add warnings
        if results.warnings:
            status_html += "<br><b>Recommendations:</b><br>"
            for warning in results.warnings:
                status_html += f"  • {warning}<br>"

        # Update widget
        self._alignment_status_label.setText(status_html)
        self._set_alignment_state(status_html, self._tone_for_alignment_quality(results.quality))

        # Show quick metrics in details label
        details_text = (
            f"Vertical: {results.vertical_mean_px:.1f} px ({results.vertical_status}) | "
            f"Toe-in: {results.convergence_std_px:.1f} px ({results.horizontal_status}) | "
            f"Rotation: {results.rotation_deg:.1f}° ({results.rotation_status}) | "
            f"Focal Length: {results.scale_difference_percent:.1f}% diff ({results.scale_status})"
        )
        self._alignment_details.setText(details_text)
        self._alignment_details.show()

        # NEW: Update quality gauge
        quality_score = results.get_quality_score()
        issues_count = sum(
            [
                results.scale_difference_percent > 2.0,
                results.convergence_std_px > 5.0,
                abs(results.vertical_mean_px) > 5.0,
                abs(results.rotation_deg) > 1.0 and not results.rotation_correction_needed,
            ]
        )

        # Choose gauge color based on score
        if quality_score >= 90:
            gauge_color = self._theme.accent_success  # Green
            gauge_emoji = "✅"
        elif quality_score >= 75:
            gauge_color = self._theme.accent_success  # Light green
            gauge_emoji = "✓"
        elif quality_score >= 60:
            gauge_color = self._theme.accent_warning  # Yellow
            gauge_emoji = "🟡"
        elif quality_score >= 40:
            gauge_color = self._theme.accent_warning  # Orange
            gauge_emoji = "⚠️"
        else:
            gauge_color = self._theme.accent_error  # Red
            gauge_emoji = "❌"

        gauge_html = f"""
        <div style='text-align: center;'>
            <div style='font-size: 32pt; color: {gauge_color};'>{gauge_emoji}</div>
            <div style='font-size: 20pt; color: {gauge_color}; font-weight: bold;'>{quality_score}%</div>
            <div style='font-size: 11pt; color: {self._theme.text_primary}; font-weight: bold;'>{results.quality}</div>
            <div style='font-size: 10pt; color: {self._theme.text_primary};'>
                {issues_count} issue{'s' if issues_count != 1 else ''} detected
            </div>
        </div>
        """
        self._quality_gauge.setText(gauge_html)
        self._set_quality_gauge_state(gauge_html, self._tone_for_quality_score(quality_score))
        self._quality_gauge.show()

        # NEW: Show directional guidance if alignment needs adjustment
        guidance = results.get_directional_guidance()
        if guidance and results.quality in ["POOR", "ACCEPTABLE"]:
            guidance_html = "<b>📋 Adjustment Instructions:</b><br>"
            for instruction in guidance:
                guidance_html += f"{instruction}<br>"
            self._guidance_label.setText(guidance_html)
            self._guidance_label.show()
        else:
            self._guidance_label.hide()

        # NEW: Show calibration quality prediction
        from analysis.camera_alignment import predict_calibration_quality

        prediction = predict_calibration_quality(results)
        prediction_html = (
            f"<b>🎯 Predicted Calibration Quality:</b><br>"
            f"Estimated RMS Error: {prediction['estimated_rms_min']:.2f} - "
            f"{prediction['estimated_rms_max']:.2f} px<br>"
            f"Expected Rating: {prediction['predicted_quality']}<br>"
            f"<i>{prediction['confidence_message']}</i>"
        )
        self._prediction_label.setText(prediction_html)
        self._prediction_label.show()

        # NEW: Show features button
        self._show_features_btn.show()

        # NEW: Update alignment history
        self._update_alignment_history(results)
