"""Camera analysis helpers for the calibration step."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from log_config.logger import get_logger

logger = get_logger(__name__)


class CalibrationStepCameraAnalysisMixin:
    def _get_marker_horizontal_position(self, image: np.ndarray, return_details: bool = False) -> Optional[float | tuple]:
        """Get average horizontal position of ChArUco markers (0.0 = left, 1.0 = right).

        Args:
            image: Camera image
            return_details: If True, return (position, marker_count, marker_corners, marker_ids)

        Returns:
            Average horizontal position (0.0-1.0) or None if no markers detected
            If return_details=True: (position, count, corners, ids) tuple
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Use cached dictionary or default
        dict_id = cv2.aruco.DICT_6X6_250
        if self._cached_dict_name:
            # Map dict name to ID
            dict_map = {
                'DICT_6X6_250': cv2.aruco.DICT_6X6_250,
                'DICT_5X5_250': cv2.aruco.DICT_5X5_250,
                'DICT_4X4_250': cv2.aruco.DICT_4X4_250,
                'DICT_6X6_100': cv2.aruco.DICT_6X6_100,
                'DICT_5X5_100': cv2.aruco.DICT_5X5_100,
                'DICT_4X4_100': cv2.aruco.DICT_4X4_100,
                'DICT_4X4_50': cv2.aruco.DICT_4X4_50,
                'DICT_ARUCO_ORIGINAL': cv2.aruco.DICT_ARUCO_ORIGINAL,
            }
            dict_id = dict_map.get(self._cached_dict_name, cv2.aruco.DICT_6X6_250)

        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)

        # Detect markers
        try:
            detector_params = cv2.aruco.DetectorParameters()
            detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
            marker_corners, marker_ids, _ = detector.detectMarkers(gray)
        except AttributeError:
            # Older OpenCV API
            detector_params = cv2.aruco.DetectorParameters_create()
            marker_corners, marker_ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=detector_params)

        if marker_ids is None or len(marker_ids) == 0:
            return None if not return_details else (None, 0, None, None)

        # Calculate average horizontal position of marker centers
        image_width = image.shape[1]
        horizontal_positions = []

        for corners in marker_corners:
            # Corners is shape (1, 4, 2) - get center point
            center_x = corners[0][:, 0].mean()
            # Normalize to 0.0-1.0
            normalized_x = center_x / image_width
            horizontal_positions.append(normalized_x)

        # Return average position
        avg_position = np.mean(horizontal_positions)

        if return_details:
            return (avg_position, len(marker_ids), marker_corners, marker_ids)
        return avg_position

    def _draw_marker_position_overlay(self, display_image: np.ndarray, original_image: np.ndarray) -> np.ndarray:
        """Draw visual indicator showing marker horizontal position.

        Args:
            display_image: Image to draw on (annotated image from _detect_charuco)
            original_image: Original camera frame for detection

        Returns:
            Image with position overlay
        """
        # Get marker position details
        result = self._get_marker_horizontal_position(original_image, return_details=True)

        if result[0] is None:  # No markers detected
            return display_image

        avg_position, marker_count, marker_corners, marker_ids = result

        # Draw position indicator bar at bottom
        height, width = display_image.shape[:2]
        bar_height = 30
        bar_y = height - bar_height

        # Draw background bar
        cv2.rectangle(
            display_image,
            (0, bar_y),
            (width, height),
            (50, 50, 50),  # Dark gray background
            -1
        )

        # Draw position marker
        marker_x = int(avg_position * width)
        marker_color = (0, 255, 0)  # Green

        # Determine if position indicates correct orientation
        if avg_position < 0.4:
            marker_color = (0, 165, 255)  # Orange - markers on left
            position_text = "LEFT"
        elif avg_position > 0.6:
            marker_color = (0, 255, 0)  # Green - markers on right (good for left camera)
            position_text = "RIGHT"
        else:
            marker_color = (0, 255, 255)  # Yellow - centered
            position_text = "CENTER"

        # Draw vertical line at marker position
        cv2.line(
            display_image,
            (marker_x, bar_y),
            (marker_x, height),
            marker_color,
            3
        )

        # Draw position text
        text = f"{position_text} ({avg_position:.1%}) | {marker_count} markers"
        cv2.putText(
            display_image,
            text,
            (10, bar_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

        return display_image

    def _update_focus_indicators(self, left_blur: float, right_blur: float) -> None:
        """Update focus quality indicators for both cameras.

        Args:
            left_blur: Blur score for left camera (Laplacian variance)
            right_blur: Blur score for right camera (Laplacian variance)
        """
        # Focus quality thresholds
        EXCELLENT_THRESHOLD = 300  # >300 is excellent
        GOOD_THRESHOLD = 150       # 150-300 is good
        POOR_THRESHOLD = 100       # 100-150 is acceptable, <100 is poor

        def get_focus_status(blur_score: float) -> tuple[str, str]:
            """Get focus status text and semantic tone."""
            if blur_score >= EXCELLENT_THRESHOLD:
                return (f"Focus: Excellent ({blur_score:.0f})", "success")
            elif blur_score >= GOOD_THRESHOLD:
                return (f"Focus: Good ({blur_score:.0f})", "success")
            elif blur_score >= POOR_THRESHOLD:
                return (f"Focus: Acceptable ({blur_score:.0f})", "warning")
            else:
                return (f"⚠ ADJUST FOCUS ⚠ ({blur_score:.0f})", "error")

        # Update left camera focus indicator
        left_text, *_ = get_focus_status(left_blur)
        self._set_focus_status(
            self._left_focus,
            left_text,
            "success" if left_blur >= GOOD_THRESHOLD else ("warning" if left_blur >= POOR_THRESHOLD else "error"),
        )

        # Update right camera focus indicator
        right_text, *_ = get_focus_status(right_blur)
        self._set_focus_status(
            self._right_focus,
            right_text,
            "success" if right_blur >= GOOD_THRESHOLD else ("warning" if right_blur >= POOR_THRESHOLD else "error"),
        )

        # Determine which camera needs adjustment (if any) and only log when that
        # state changes so the preview loop does not spam diagnostics.
        if left_blur < POOR_THRESHOLD and right_blur < POOR_THRESHOLD:
            focus_state = "both"
            log_message = "Both cameras need focus adjustment (left={:.0f}, right={:.0f})"
            log_args = (left_blur, right_blur)
        elif left_blur < POOR_THRESHOLD:
            focus_state = "left"
            log_message = "Left camera needs focus adjustment (left={:.0f}, right={:.0f})"
            log_args = (left_blur, right_blur)
        elif right_blur < POOR_THRESHOLD:
            focus_state = "right"
            log_message = "Right camera needs focus adjustment (left={:.0f}, right={:.0f})"
            log_args = (left_blur, right_blur)
        else:
            focus_state = "ok"
            log_message = "Camera focus returned to acceptable range (left={:.0f}, right={:.0f})"
            log_args = (left_blur, right_blur)

        if focus_state != self._focus_warning_state:
            if focus_state == "ok" and self._focus_warning_state != "ok":
                logger.info(log_message, *log_args)
            elif focus_state != "ok":
                logger.warning(log_message, *log_args)
            self._focus_warning_state = focus_state
