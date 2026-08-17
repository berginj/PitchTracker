"""Alignment analysis routines for the calibration step."""

from __future__ import annotations

from ui.setup.steps.calibration_step_mixin_host import CalibrationStepMixinHost


import numpy as np

from log_config.logger import get_logger

logger = get_logger(__name__)


class CalibrationStepAlignmentMixin(CalibrationStepMixinHost):
    def _check_alignment_drift(self, left_img: np.ndarray, right_img: np.ndarray) -> bool:
        """Check if camera alignment has drifted since first capture.

        Drift checks based on per-pose feature matching are intentionally non-blocking.
        Calibration captures deliberately move and tilt the ChArUco board, and those scene
        changes can look like toe-in or focal-length drift even when fixed cameras have
        not moved. Keep the method as a compatibility hook, but do not interrupt capture.

        Args:
            left_img: Current left camera image
            right_img: Current right camera image

        Returns:
            Always False so calibration capture can continue.
        """
        del left_img, right_img
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
        # Choose icon based on quality (styling is applied via tones elsewhere)
        icon = {
            "CRITICAL": "❌",
            "POOR": "⚠️",
            "ACCEPTABLE": "🟡",
            "GOOD": "✓",
        }.get(
            results.quality, "✅"
        )  # EXCELLENT

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
