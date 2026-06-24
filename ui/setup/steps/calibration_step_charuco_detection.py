"""ChArUco detection logic for the calibration step."""

from __future__ import annotations


import cv2
import numpy as np

from log_config.logger import get_logger

logger = get_logger(__name__)


class CalibrationStepCharucoDetectionMixin:
    def _detect_charuco_ids(self, image: np.ndarray) -> tuple[np.ndarray | None, float]:
        """Return interpolated ChArUco corner IDs and blur score for capture validation."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        dict_name = self._cached_dict_name or "DICT_6X6_250"
        dictionary_id = getattr(cv2.aruco, dict_name, cv2.aruco.DICT_6X6_250)
        aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)
        try:
            detector_params = cv2.aruco.DetectorParameters()
            detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
            marker_corners, marker_ids, _ = detector.detectMarkers(gray)
        except AttributeError:
            detector_params = cv2.aruco.DetectorParameters_create()
            marker_corners, marker_ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=detector_params)

        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if marker_ids is None or len(marker_ids) == 0:
            return None, blur_score

        try:
            board = cv2.aruco.CharucoBoard(
                (self._pattern_cols, self._pattern_rows),
                self._square_mm,
                self._square_mm * 0.75,
                aruco_dict,
            )
        except (AttributeError, TypeError):
            board = cv2.aruco.CharucoBoard_create(
                self._pattern_cols,
                self._pattern_rows,
                self._square_mm,
                self._square_mm * 0.75,
                aruco_dict,
            )
        try:
            num_corners, _, charuco_ids = cv2.aruco.interpolateCornersCharuco(marker_corners, marker_ids, gray, board)
        except TypeError:
            num_corners, _, charuco_ids = cv2.aruco.interpolateCornersCharuco(marker_corners, marker_ids, gray, board)
        if num_corners is None or charuco_ids is None:
            return None, blur_score
        return np.asarray(charuco_ids, dtype=np.int32).reshape(-1), blur_score

    def _detect_charuco(self, image: np.ndarray) -> tuple[bool, np.ndarray, float]:
        """Detect ChArUco board and draw corners.

        Returns:
            (detected, annotated_image, blur_score)
        """
        # Convert to grayscale for detection
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Prepare annotated image
        if len(image.shape) == 2:
            annotated = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            annotated = image.copy()

        # Dictionary detection with caching to prevent processing loop
        DICTIONARIES_TO_TRY = [
            ("DICT_6X6_250", cv2.aruco.DICT_6X6_250),
            ("DICT_5X5_250", cv2.aruco.DICT_5X5_250),
            ("DICT_4X4_250", cv2.aruco.DICT_4X4_250),
            ("DICT_6X6_100", cv2.aruco.DICT_6X6_100),
            ("DICT_5X5_100", cv2.aruco.DICT_5X5_100),
            ("DICT_4X4_100", cv2.aruco.DICT_4X4_100),
            ("DICT_6X6_50", cv2.aruco.DICT_6X6_50),  # Calib.io might use this
            ("DICT_5X5_50", cv2.aruco.DICT_5X5_50),  # Calib.io might use this
            ("DICT_4X4_50", cv2.aruco.DICT_4X4_50),
            ("DICT_ARUCO_ORIGINAL", cv2.aruco.DICT_ARUCO_ORIGINAL),
        ]

        # Increment frame counter
        self._dict_scan_counter += 1
        auto_detect_enabled = self._auto_detect_pattern_checkbox.isChecked()

        # Only rescan all dictionaries when auto-detection is explicitly enabled.
        # Manual mode stays on the default dictionary to avoid noisy frame-by-frame guessing.
        if auto_detect_enabled and (self._cached_dict_name is None or self._dict_scan_counter >= 60):
            self._dict_scan_counter = 0

            best_marker_corners = None
            best_marker_ids = None
            best_rejected = None
            best_dict_name = "DICT_6X6_250"
            best_marker_count = 0

            # Log only on full scan
            if self._detection_log_counter % 10 == 0:
                logger.debug("Scanning {} ChArUco dictionaries", len(DICTIONARIES_TO_TRY))

            for dict_name, dict_id in DICTIONARIES_TO_TRY:
                aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)

                # Try newer API first (OpenCV 4.7+)
                try:
                    detector_params = cv2.aruco.DetectorParameters()
                    # Make detection more permissive
                    detector_params.adaptiveThreshWinSizeMin = 3
                    detector_params.adaptiveThreshWinSizeMax = 23
                    detector_params.adaptiveThreshWinSizeStep = 10
                    detector_params.adaptiveThreshConstant = 7
                    detector_params.minMarkerPerimeterRate = 0.01
                    detector_params.maxMarkerPerimeterRate = 4.0
                    detector_params.polygonalApproxAccuracyRate = 0.05
                    detector_params.minCornerDistanceRate = 0.05
                    detector_params.minDistanceToBorder = 1
                    detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
                    detector_params.cornerRefinementWinSize = 5
                    detector_params.cornerRefinementMaxIterations = 30
                    detector_params.cornerRefinementMinAccuracy = 0.1

                    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
                    marker_corners, marker_ids, rejected = detector.detectMarkers(gray)
                except AttributeError:
                    # Fall back to older API
                    detector_params = cv2.aruco.DetectorParameters_create()
                    detector_params.adaptiveThreshWinSizeMin = 3
                    detector_params.adaptiveThreshWinSizeMax = 23
                    detector_params.adaptiveThreshWinSizeStep = 10
                    detector_params.adaptiveThreshConstant = 7
                    detector_params.minMarkerPerimeterRate = 0.01
                    detector_params.maxMarkerPerimeterRate = 4.0
                    detector_params.polygonalApproxAccuracyRate = 0.05
                    detector_params.minCornerDistanceRate = 0.05
                    detector_params.minDistanceToBorder = 1
                    detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
                    detector_params.cornerRefinementWinSize = 5
                    detector_params.cornerRefinementMaxIterations = 30
                    detector_params.cornerRefinementMinAccuracy = 0.1

                    marker_corners, marker_ids, rejected = cv2.aruco.detectMarkers(
                        gray, aruco_dict, parameters=detector_params
                    )

                # Check if this dictionary found more markers
                num_found = len(marker_ids) if marker_ids is not None else 0
                if num_found > best_marker_count:
                    best_marker_count = num_found
                    best_marker_corners = marker_corners
                    best_marker_ids = marker_ids
                    best_rejected = rejected
                    best_dict_name = dict_name

            # Cache the best dictionary found
            # Log if dictionary changed
            dict_changed = self._cached_dict_name != best_dict_name
            if dict_changed and best_marker_count > 0:
                logger.info(
                    "ChArUco dictionary changed from {} to {} after detecting {} markers",
                    self._cached_dict_name or "None",
                    best_dict_name,
                    best_marker_count,
                )

            self._cached_dict_name = best_dict_name
            marker_corners = best_marker_corners
            marker_ids = best_marker_ids
            rejected = best_rejected

            # Log only occasionally
            if self._detection_log_counter % 10 == 0:
                num_detected = len(marker_ids) if marker_ids is not None else 0
                num_rejected = len(rejected) if rejected is not None and len(rejected) > 0 else 0
                logger.debug(
                    "Using ChArUco dictionary {}: detected={} rejected={}",
                    best_dict_name,
                    num_detected,
                    num_rejected,
                )
        else:
            # Use cached dictionary for fast detection
            dict_name_to_use = self._cached_dict_name or "DICT_6X6_250"
            dict_id = next(d[1] for d in DICTIONARIES_TO_TRY if d[0] == dict_name_to_use)
            self._cached_dict_name = dict_name_to_use
            aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)

            # Try newer API first (OpenCV 4.7+)
            try:
                detector_params = cv2.aruco.DetectorParameters()
                detector_params.adaptiveThreshWinSizeMin = 3
                detector_params.adaptiveThreshWinSizeMax = 23
                detector_params.adaptiveThreshWinSizeStep = 10
                detector_params.adaptiveThreshConstant = 7
                detector_params.minMarkerPerimeterRate = 0.03
                detector_params.maxMarkerPerimeterRate = 4.0
                detector_params.polygonalApproxAccuracyRate = 0.05
                detector_params.minCornerDistanceRate = 0.05
                detector_params.minDistanceToBorder = 3
                detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
                detector_params.cornerRefinementWinSize = 5
                detector_params.cornerRefinementMaxIterations = 30
                detector_params.cornerRefinementMinAccuracy = 0.1

                detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
                marker_corners, marker_ids, rejected = detector.detectMarkers(gray)
            except AttributeError:
                # Fall back to older API
                detector_params = cv2.aruco.DetectorParameters_create()
                detector_params.adaptiveThreshWinSizeMin = 3
                detector_params.adaptiveThreshWinSizeMax = 23
                detector_params.adaptiveThreshWinSizeStep = 10
                detector_params.adaptiveThreshConstant = 7
                detector_params.minMarkerPerimeterRate = 0.03
                detector_params.maxMarkerPerimeterRate = 4.0
                detector_params.polygonalApproxAccuracyRate = 0.05
                detector_params.minCornerDistanceRate = 0.05
                detector_params.minDistanceToBorder = 3
                detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
                detector_params.cornerRefinementWinSize = 5
                detector_params.cornerRefinementMaxIterations = 30
                detector_params.cornerRefinementMinAccuracy = 0.1

                marker_corners, marker_ids, rejected = cv2.aruco.detectMarkers(
                    gray, aruco_dict, parameters=detector_params
                )

        # Get dict name for display (either from cache or from scan)
        best_dict_name = self._cached_dict_name if self._cached_dict_name else "DICT_6X6_250"

        # Increment log counter
        self._detection_log_counter += 1

        # Get aruco_dict for later use in board creation
        aruco_dict = cv2.aruco.getPredefinedDictionary(
            next(d[1] for d in DICTIONARIES_TO_TRY if d[0] == best_dict_name)
        )

        # Get detection counts
        num_detected = len(marker_ids) if marker_ids is not None else 0
        num_rejected = len(rejected) if rejected is not None and len(rejected) > 0 else 0

        # Calculate blur metric (Laplacian variance) - low values indicate blur
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        is_blurry = blur_score < 100  # Threshold for blur detection

        # Add header showing what we're looking for and what dictionary is being used
        header_text = f"Looking for {self._pattern_cols}x{self._pattern_rows} ChArUco ({self._square_mm:.0f}mm) - Using {best_dict_name}"
        header_size = cv2.getTextSize(header_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        header_x = (gray.shape[1] - header_size[0]) // 2  # Center horizontally
        header_y = 25
        # Draw background for header
        cv2.rectangle(annotated, (header_x - 10, 5), (header_x + header_size[0] + 10, 35), (50, 50, 50), -1)
        cv2.rectangle(annotated, (header_x - 10, 5), (header_x + header_size[0] + 10, 35), (200, 200, 200), 2)
        cv2.putText(annotated, header_text, (header_x, header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw rejected markers in red to show what was found but not accepted
        if rejected is not None and len(rejected) > 0:
            for corners in rejected:
                pts = corners.reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(annotated, [pts], True, (0, 0, 255), 2)

        # Check if any markers were detected
        if marker_ids is None or len(marker_ids) == 0:
            # Add diagnostic info
            if num_rejected > 0:
                hint_text = f"Found {num_rejected} marker-like shapes but ALL REJECTED (see red)"
                cv2.putText(annotated, hint_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(
                    annotated,
                    "Tried all common ArUco dictionaries - none matched",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 165, 255),
                    1,
                )
                cv2.putText(
                    annotated,
                    "Possible causes: Wrong print scale, damaged print, glare/shadows",
                    (10, 115),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 165, 255),
                    1,
                )
            else:
                hint_text = "Move ChArUco board into view"
                cv2.putText(annotated, hint_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # Show blur warning if image is blurry
            if is_blurry:
                cv2.putText(
                    annotated,
                    f"WARNING: Image blurry! (score={blur_score:.0f})",
                    (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 165, 255),
                    2,
                )
                cv2.putText(
                    annotated,
                    "Try: Adjust camera focus, better lighting",
                    (10, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 165, 255),
                    1,
                )

            # FALLBACK: Try plain checkerboard detection if ChArUco markers failed
            if self._detection_log_counter % 30 == 0:
                logger.debug("No ChArUco markers detected; trying checkerboard fallback")
            try:
                fallback_result = self._try_checkerboard_fallback(gray, annotated, blur_score, is_blurry)
                if fallback_result is not None:
                    return fallback_result  # Returns (True, annotated_image, blur_score)
            except Exception as e:
                logger.warning("Checkerboard fallback raised an exception after ChArUco miss: {}", e)

            return False, annotated, blur_score

        # Log which markers were found (reduced frequency)
        if self._detection_log_counter % 30 == 0:
            marker_id_list = marker_ids.flatten().tolist() if marker_ids is not None else []
            logger.debug("Detected ChArUco marker IDs: {}", marker_id_list)

        # AUTO-DETECT: Try to infer pattern size from detected markers only
        # when the operator explicitly enables it in Advanced Settings.
        import time

        current_time = time.time()

        # Auto-detect pattern only if checkbox is enabled and pattern not locked
        if (
            self._auto_detect_pattern_checkbox.isChecked()
            and not self._pattern_locked
            and current_time - self._last_auto_detect_time >= 3.0
        ):
            auto_detected_pattern = self._auto_detect_charuco_pattern(marker_ids)
            if auto_detected_pattern:
                auto_cols, auto_rows, auto_square_mm = auto_detected_pattern
                # Update if different from current settings
                if (
                    auto_cols != self._pattern_cols
                    or auto_rows != self._pattern_rows
                    or abs(auto_square_mm - self._square_mm) > 0.5
                ):
                    logger.info(
                        "Auto-detected ChArUco pattern {}x{} at {:.1f}mm; locking settings",
                        auto_cols,
                        auto_rows,
                        auto_square_mm,
                    )
                    self._pattern_cols = auto_cols
                    self._pattern_rows = auto_rows
                    self._square_mm = auto_square_mm
                    # Update UI controls
                    self._pattern_cols_spin.blockSignals(True)
                    self._pattern_rows_spin.blockSignals(True)
                    self._square_spin.blockSignals(True)
                    self._pattern_cols_spin.setValue(auto_cols)
                    self._pattern_rows_spin.setValue(auto_rows)
                    self._square_spin.setValue(auto_square_mm)
                    self._pattern_cols_spin.blockSignals(False)
                    self._pattern_rows_spin.blockSignals(False)
                    self._square_spin.blockSignals(False)
                    self._update_pattern_info()
                    self._last_auto_detect_time = current_time
                    # LOCK THE PATTERN - stop scanning
                    self._pattern_locked = True
                    logger.info("Locked ChArUco pattern at {}x{}", auto_cols, auto_rows)

                    # Store detected pattern for multi-pattern support
                    pattern_info = {
                        "cols": auto_cols,
                        "rows": auto_rows,
                        "square_mm": auto_square_mm,
                        "dictionary": self._cached_dict_name or "DICT_6X6_250",
                    }
                    # Add to list if not already present
                    if pattern_info not in self._detected_patterns:
                        self._detected_patterns.append(pattern_info)
                        logger.debug("Stored detected ChArUco pattern variant {}", pattern_info)

        # Draw detected markers in green
        cv2.aruco.drawDetectedMarkers(annotated, marker_corners, marker_ids)

        # Create ChArUco board
        try:
            # Try newer API first (OpenCV 4.7+)
            board = cv2.aruco.CharucoBoard(
                (self._pattern_cols, self._pattern_rows),
                self._square_mm,
                self._square_mm * 0.75,  # Marker size is 75% of square
                aruco_dict,
            )
        except (AttributeError, TypeError):
            # Fall back to older API
            board = cv2.aruco.CharucoBoard_create(
                self._pattern_cols, self._pattern_rows, self._square_mm, self._square_mm * 0.75, aruco_dict
            )

        # Interpolate ChArUco corners
        # Log only occasionally to avoid spam
        if self._detection_log_counter % 30 == 0:
            logger.debug(
                "Creating ChArUco board {}x{} square_mm={:.1f} marker_mm={:.1f}",
                self._pattern_cols,
                self._pattern_rows,
                self._square_mm,
                self._square_mm * 0.75,
            )
        try:
            # Try newer API first (OpenCV 4.7+)
            num_corners, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                marker_corners, marker_ids, gray, board
            )
        except TypeError:
            # Fall back to older API
            num_corners, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                marker_corners, marker_ids, gray, board
            )

        # Check if enough corners were detected
        # Need at least 4 corners for calibration
        MIN_CORNERS = 4

        # Add detection diagnostics at bottom with background
        num_markers = len(marker_ids) if marker_ids is not None else 0
        corner_count = num_corners if num_corners is not None else 0
        diag_text = (
            f"Markers: {num_markers} (Rejected: {num_rejected}) | Corners: {corner_count} | Blur: {blur_score:.0f}"
        )
        blur_status = " (BLURRY!)" if is_blurry else " (OK)"
        full_text = diag_text + blur_status

        # Draw background rectangle for text
        text_size = cv2.getTextSize(full_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        bg_x1, bg_y1 = 5, gray.shape[0] - 35
        bg_x2, bg_y2 = text_size[0] + 15, gray.shape[0] - 5
        cv2.rectangle(annotated, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
        cv2.rectangle(annotated, (bg_x1, bg_y1), (bg_x2, bg_y2), (255, 255, 255), 2)

        # Draw text on background
        text_color = (0, 0, 255) if is_blurry else (0, 255, 0)  # Red if blurry, green if OK
        cv2.putText(annotated, full_text, (10, gray.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

        if num_corners is not None and num_corners >= MIN_CORNERS:
            # Draw ChArUco corners
            cv2.aruco.drawDetectedCornersCharuco(annotated, charuco_corners, charuco_ids, (0, 255, 0))

            # Add success indicator with background
            success_text = f"READY - {num_corners} corners detected"
            text_size = cv2.getTextSize(success_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 128, 0), -1)
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 255, 0), 2)
            cv2.putText(annotated, success_text, (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Warn if blurry even though detected
            if is_blurry:
                cv2.putText(
                    annotated,
                    "WARNING: Blurry - may affect calibration",
                    (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 165, 255),
                    2,
                )

            return True, annotated, blur_score
        else:
            # Not enough corners detected - provide detailed diagnostics
            corner_count = num_corners if num_corners is not None else 0
            error_text = f"Need {MIN_CORNERS}+ corners (found {corner_count})"
            text_size = cv2.getTextSize(error_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 0, 128), -1)
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 165, 255), 2)
            cv2.putText(annotated, error_text, (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Provide specific suggestions based on detection state
            y_offset = 105
            if is_blurry:
                cv2.putText(
                    annotated,
                    "ISSUE: Image is blurry - adjust camera focus!",
                    (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )
                y_offset += 30

            if num_markers < 4:
                cv2.putText(
                    annotated,
                    f"ISSUE: Only {num_markers} markers detected (need more)",
                    (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 165, 255),
                    2,
                )
                cv2.putText(
                    annotated,
                    "Try: Move board closer, better lighting, sharper focus",
                    (10, y_offset + 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 165, 255),
                    1,
                )
            else:
                cv2.putText(
                    annotated,
                    f"Markers OK ({num_markers} found), but corners failed",
                    (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 165, 255),
                    2,
                )
                cv2.putText(
                    annotated,
                    "Try: Ensure full board visible, check pattern size",
                    (10, y_offset + 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 165, 255),
                    1,
                )

            # FALLBACK: Try plain checkerboard detection if ChArUco corner interpolation failed
            if self._detection_log_counter % 30 == 0:
                logger.debug(
                    "ChArUco detection found {} markers but only {} corners; trying checkerboard fallback",
                    num_markers,
                    corner_count,
                )
            try:
                fallback_result = self._try_checkerboard_fallback(gray, annotated, blur_score, is_blurry)
                if fallback_result is not None:
                    return fallback_result  # Returns (True, annotated_image, blur_score)
            except Exception as e:
                logger.warning(
                    "Checkerboard fallback raised an exception after insufficient ChArUco corners: {}",
                    e,
                )

            return False, annotated, blur_score
