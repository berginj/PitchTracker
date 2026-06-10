"""Preview refresh and capture handlers for the calibration step."""

from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from log_config.logger import get_logger
from ui.themes import (
    show_message_dialog,
)

logger = get_logger(__name__)


class CalibrationStepPreviewCaptureMixin:
    def _update_preview(self) -> None:
        """Update camera previews and check for ChArUco board."""
        if not self._left_camera or not self._right_camera:
            # Only log once to avoid spam
            if not hasattr(self, '_logged_missing_cameras'):
                logger.debug(
                    "Skipping preview update because calibration cameras are missing. left_camera={!r}, right_camera={!r}",
                    self._left_camera,
                    self._right_camera,
                )
                self._logged_missing_cameras = True
            return

        try:
            # Get frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            if left_frame is None or right_frame is None:
                return

            # Check for ChArUco board in both cameras
            left_detected, left_image, left_blur = self._detect_charuco(left_frame.image)
            right_detected, right_image, right_blur = self._detect_charuco(right_frame.image)

            # Add visual marker position overlay (if enabled)
            if self._show_marker_overlay:
                left_image = self._draw_marker_position_overlay(left_image.copy(), left_frame.image)
                right_image = self._draw_marker_position_overlay(right_image.copy(), right_frame.image)

            # Update previews
            self._update_view(self._left_view, left_image)
            self._update_view(self._right_view, right_image)

            # Update status indicators - Simplified READY/NOT READY
            if left_detected:
                self._left_status.setText("✅ READY")
                self._set_detection_status(self._left_status, detected=True)
            else:
                self._left_status.setText("⏳ Waiting for board...")
                self._set_detection_status(self._left_status, detected=False)

            if right_detected:
                self._right_status.setText("✅ READY")
                self._set_detection_status(self._right_status, detected=True)
            else:
                self._right_status.setText("⏳ Waiting for board...")
                self._set_detection_status(self._right_status, detected=False)

            # Update focus quality indicators
            self._update_focus_indicators(left_blur, right_blur)

            # Enable capture if both detected
            self._capture_button.setEnabled(left_detected and right_detected)

        except Exception:
            pass

    def _auto_detect_charuco_pattern(self, marker_ids: np.ndarray) -> Optional[tuple[int, int, float]]:
        """Auto-detect ChArUco pattern size without guessing physical square size.

        Args:
            marker_ids: Detected ArUco marker IDs

        Returns:
            (cols, rows, square_mm) tuple or None if cannot detect. The square_mm
            value remains the user-entered/measured value.
        """
        if marker_ids is None or len(marker_ids) == 0:
            return None

        # ChArUco boards have (cols-1)*(rows-1) markers
        # Marker IDs are sequential: 0, 1, 2, ..., (cols-1)*(rows-1)-1
        max_id = int(np.max(marker_ids))
        num_markers = max_id + 1

        # Try common ChArUco configurations
        # Format: (cols, rows) where num_markers = (cols-1)*(rows-1)
        COMMON_PATTERNS = [
            (9, 6),   # 8*5 = 40 markers
            (7, 5),   # 6*4 = 24 markers
            (11, 8),  # 10*7 = 70 markers
            (8, 6),   # 7*5 = 35 markers
            (10, 7),  # 9*6 = 54 markers
            (12, 9),  # 11*8 = 88 markers
        ]

        detected_pattern = None
        for cols, rows in COMMON_PATTERNS:
            expected_markers = (cols - 1) * (rows - 1)
            # Allow some missing markers (partial view)
            if abs(num_markers - expected_markers) <= 5:
                detected_pattern = (cols, rows)
                break

        if not detected_pattern:
            # Fallback: try to infer from marker count
            # Find factors of (num_markers + small_tolerance)
            for tolerance in range(6):
                test_count = num_markers + tolerance
                for divisor in range(4, 12):  # Reasonable range for (cols-1) or (rows-1)
                    if test_count % divisor == 0:
                        other = test_count // divisor
                        if 4 <= other <= 12:
                            # Found plausible dimensions
                            cols = divisor + 1
                            rows = other + 1
                            detected_pattern = (cols, rows)
                            break
                if detected_pattern:
                    break

        if not detected_pattern:
            return None

        cols, rows = detected_pattern

        square_mm = float(self._square_mm)

        logger.debug(
            "Auto-detected ChArUco candidate from markers: count={}, max_id={}, pattern={}x{}, keeping measured square_mm={:.1f}",
            len(marker_ids),
            max_id,
            cols,
            rows,
            square_mm,
        )

        return (cols, rows, square_mm)

    def _validate_capture_pair(self, left_image: np.ndarray, right_image: np.ndarray) -> tuple[bool, str]:
        """Validate the exact frames that will be saved for calibration."""
        left_ids, left_blur = self._detect_charuco_ids(left_image)
        right_ids, right_blur = self._detect_charuco_ids(right_image)
        if left_blur < 100 or right_blur < 100:
            return (
                False,
                f"Capture rejected because focus is too soft (left={left_blur:.0f}, right={right_blur:.0f}).",
            )
        if left_ids is None or right_ids is None:
            return False, "Capture rejected because the ChArUco board was not detected in both saved frames."
        shared = set(int(x) for x in left_ids) & set(int(x) for x in right_ids)
        if len(shared) < 8:
            return (
                False,
                f"Capture rejected because only {len(shared)} shared ChArUco corners were visible in both cameras.",
            )
        return True, f"{len(shared)} shared ChArUco corners"

    def _try_checkerboard_fallback(
        self,
        gray: np.ndarray,
        annotated: np.ndarray,
        blur_score: float,
        is_blurry: bool
    ) -> Optional[tuple[bool, np.ndarray, float]]:
        """Try plain checkerboard detection as fallback when ChArUco fails.

        Args:
            gray: Grayscale image
            annotated: Annotated color image
            blur_score: Focus quality score
            is_blurry: Whether image is blurry

        Returns:
            (True, annotated_image, blur_score) if successful, None if failed
        """
        try:
            # Validate inputs
            if gray is None or annotated is None or gray.size == 0 or annotated.size == 0:
                logger.warning("Checkerboard fallback received invalid input images")
                return None

            # Checkerboard has (cols-1, rows-1) internal corners
            board_size = (self._pattern_cols - 1, self._pattern_rows - 1)

            # Try to find checkerboard corners
            # flags: Use adaptive threshold + normalize image for better detection
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE

            ret, corners = cv2.findChessboardCorners(gray, board_size, flags)

            if not ret or corners is None:
                logger.debug("Checkerboard fallback could not detect pattern {}", board_size)
                return None

            # Refine corner locations to sub-pixel accuracy
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            # Draw detected corners
            cv2.drawChessboardCorners(annotated, board_size, corners_refined, ret)

            num_corners = len(corners_refined)
            logger.debug(
                "Checkerboard fallback succeeded with {} corners for pattern {}",
                num_corners,
                board_size,
            )

            # Add success indicator with "CHECKERBOARD MODE" label
            success_text = f"READY - {num_corners} corners (CHECKERBOARD MODE)"
            text_size = cv2.getTextSize(success_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 128, 128), -1)  # Teal background
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 255, 255), 2)  # Cyan border
            cv2.putText(annotated, success_text, (10, 75),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Add diagnostic info at bottom
            diag_text = f"Plain Checkerboard: {num_corners} corners | Blur: {blur_score:.0f}"
            blur_status = " (BLURRY!)" if is_blurry else " (OK)"
            full_text = diag_text + blur_status

            text_size = cv2.getTextSize(full_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            bg_x1, bg_y1 = 5, gray.shape[0] - 35
            bg_x2, bg_y2 = text_size[0] + 15, gray.shape[0] - 5
            cv2.rectangle(annotated, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
            cv2.rectangle(annotated, (bg_x1, bg_y1), (bg_x2, bg_y2), (255, 255, 255), 2)

            text_color = (0, 0, 255) if is_blurry else (0, 255, 255)  # Red if blurry, cyan if OK
            cv2.putText(annotated, full_text, (10, gray.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

            # Warn if blurry
            if is_blurry:
                cv2.putText(annotated, "WARNING: Blurry - may affect calibration", (10, 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

            return (True, annotated, blur_score)

        except Exception as e:
            logger.warning("Checkerboard fallback failed unexpectedly: {}", e)
            return None

    def _update_view(self, label: QtWidgets.QLabel, image: np.ndarray) -> None:
        """Update QLabel with image."""
        try:
            # Convert to QPixmap
            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                height, width, channels = image_rgb.shape
                bytes_per_line = channels * width
                q_image = QtGui.QImage(
                    image_rgb.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_RGB888,
                )
            else:
                height, width = image.shape
                bytes_per_line = width
                q_image = QtGui.QImage(
                    image.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_Grayscale8,
                )

            pixmap = QtGui.QPixmap.fromImage(q_image)
            scaled = pixmap.scaled(
                label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(scaled)

        except Exception:
            pass

    def _capture_image_pair(self) -> None:
        """Capture current image pair."""
        if not self._left_camera or not self._right_camera:
            return

        try:
            # Get frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            if left_frame is None or right_frame is None:
                show_message_dialog(
                    self,
                    "Capture Failed",
                    "Failed to read from cameras.",
                    tone="warning",
                )
                return

            valid, validation_message = self._validate_capture_pair(left_frame.image, right_frame.image)
            if not valid:
                show_message_dialog(
                    self,
                    "Capture Rejected",
                    validation_message,
                    tone="warning",
                )
                return

            # NEW: Check for alignment drift (after first capture)
            if len(self._captures) > 0:
                drift_detected = self._check_alignment_drift(left_frame.image, right_frame.image)
                if drift_detected:
                    return  # User chose to abort this capture

            # Save to temp directory
            timestamp = int(time.time() * 1000)
            left_path = self._temp_dir / f"left_{timestamp}.png"
            right_path = self._temp_dir / f"right_{timestamp}.png"

            cv2.imwrite(str(left_path), left_frame.image)
            cv2.imwrite(str(right_path), right_frame.image)

            # Store capture
            self._captures.append((left_frame.image, right_frame.image))

            # Update UI - Both progress bar and label
            count = len(self._captures)
            self._capture_progress_bar.setValue(count)

            if count < self._min_captures:
                self._capture_count_label.setText(f"Progress: {count}/{self._min_captures} poses captured")
            else:
                self._capture_count_label.setText(f"Progress: {count}/{self._min_captures} poses ✓ Ready!")
            self._set_capture_progress_state(count, ready=count >= self._min_captures)

            # Enable calibrate button if enough captures
            if count >= self._min_captures:
                self._calibrate_button.setEnabled(True)

            # Visual feedback
            self._style_manager.style_button(self._capture_button, "primary")
            QtCore.QTimer.singleShot(
                200,
                lambda: self._style_manager.style_button(self._capture_button, "success"),
            )

            # Store baseline alignment from first capture and track alignment history
            try:
                from analysis.camera_alignment import analyze_alignment
                current_alignment = analyze_alignment(left_frame.image, right_frame.image)
                self._alignment_history.append(current_alignment)

                if len(self._captures) == 1:
                    self._baseline_alignment = current_alignment
            except Exception:
                pass  # Don't fail capture if alignment analysis fails

        except Exception as e:
            show_message_dialog(
                self,
                "Capture Error",
                f"Failed to capture image pair:\n{str(e)}",
                tone="error",
            )
