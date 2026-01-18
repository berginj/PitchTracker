"""Step 2: Stereo Calibration - Capture checkerboard images and calibrate."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from calib.quick_calibrate import calibrate_and_write
from capture import CameraDevice
from ui.setup.steps.base_step import BaseStep


class CalibrationStep(BaseStep):
    """Step 2: Stereo calibration with checkerboard pattern.

    Workflow:
    1. Show live preview from both cameras
    2. Detect checkerboard in real-time
    3. Capture image pairs when user clicks "Capture"
    4. Run calibration when minimum images captured
    5. Show results and save to config
    """

    def __init__(
        self,
        backend: str = "uvc",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._backend = backend
        self._left_camera: Optional[CameraDevice] = None
        self._right_camera: Optional[CameraDevice] = None
        self._left_serial: Optional[str] = None
        self._right_serial: Optional[str] = None

        # Calibration settings
        self._pattern_cols = 9
        self._pattern_rows = 6
        self._square_mm = 25.0  # 25mm square size
        self._min_captures = 10
        self._config_path = Path("configs/default.yaml")

        # Capture state
        self._captures: list[tuple[np.ndarray, np.ndarray]] = []
        self._temp_dir = Path("calibration/temp")
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        # Calibration results
        self._calibration_result: Optional[dict] = None

        self._build_ui()

        # Preview timer
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)

    def _build_ui(self) -> None:
        """Build calibration step UI."""
        layout = QtWidgets.QVBoxLayout()

        # Instructions
        instructions = QtWidgets.QLabel(
            "Stereo Calibration:\n\n"
            "1. Hold the checkerboard pattern in view of both cameras\n"
            "2. When both indicators turn GREEN, click 'Capture'\n"
            "3. Capture at least 10 image pairs from different angles\n"
            "4. Click 'Calibrate' to compute stereo parameters"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 11pt; padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(instructions)

        # Settings row
        settings_group = self._build_settings_group()
        layout.addWidget(settings_group)

        # Camera previews
        preview_layout = QtWidgets.QHBoxLayout()

        # Left preview
        left_group = QtWidgets.QGroupBox("Left Camera")
        self._left_view = QtWidgets.QLabel("No preview")
        self._left_view.setMinimumSize(320, 240)
        self._left_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_view.setStyleSheet("background-color: #f5f5f5;")

        self._left_status = QtWidgets.QLabel("● Waiting...")
        self._left_status.setStyleSheet("color: gray; font-weight: bold;")

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._left_view)
        left_layout.addWidget(self._left_status, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        left_group.setLayout(left_layout)

        # Right preview
        right_group = QtWidgets.QGroupBox("Right Camera")
        self._right_view = QtWidgets.QLabel("No preview")
        self._right_view.setMinimumSize(320, 240)
        self._right_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_view.setStyleSheet("background-color: #f5f5f5;")

        self._right_status = QtWidgets.QLabel("● Waiting...")
        self._right_status.setStyleSheet("color: gray; font-weight: bold;")

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self._right_view)
        right_layout.addWidget(self._right_status, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        right_group.setLayout(right_layout)

        preview_layout.addWidget(left_group)
        preview_layout.addWidget(right_group)
        layout.addLayout(preview_layout)

        # Controls
        controls_layout = QtWidgets.QHBoxLayout()

        self._capture_button = QtWidgets.QPushButton("📷 Capture")
        self._capture_button.setMinimumHeight(40)
        self._capture_button.setEnabled(False)
        self._capture_button.clicked.connect(self._capture_image_pair)

        self._capture_count_label = QtWidgets.QLabel("Captured: 0")
        self._capture_count_label.setStyleSheet("font-size: 12pt; font-weight: bold;")

        self._calibrate_button = QtWidgets.QPushButton("🔧 Calibrate")
        self._calibrate_button.setMinimumHeight(40)
        self._calibrate_button.setEnabled(False)
        self._calibrate_button.clicked.connect(self._run_calibration)

        controls_layout.addWidget(self._capture_button, 2)
        controls_layout.addWidget(self._capture_count_label, 1)
        controls_layout.addWidget(self._calibrate_button, 2)
        layout.addLayout(controls_layout)

        # Results display
        self._results_text = QtWidgets.QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setMaximumHeight(100)
        self._results_text.hide()
        layout.addWidget(self._results_text)

        self.setLayout(layout)

    def _build_settings_group(self) -> QtWidgets.QGroupBox:
        """Build calibration settings group."""
        group = QtWidgets.QGroupBox("Checkerboard Settings")

        # Pattern size
        pattern_label = QtWidgets.QLabel("Pattern (cols x rows):")
        self._pattern_cols_spin = QtWidgets.QSpinBox()
        self._pattern_cols_spin.setRange(3, 20)
        self._pattern_cols_spin.setValue(self._pattern_cols)
        self._pattern_cols_spin.valueChanged.connect(lambda v: setattr(self, '_pattern_cols', v))

        cross_label = QtWidgets.QLabel("×")

        self._pattern_rows_spin = QtWidgets.QSpinBox()
        self._pattern_rows_spin.setRange(3, 20)
        self._pattern_rows_spin.setValue(self._pattern_rows)
        self._pattern_rows_spin.valueChanged.connect(lambda v: setattr(self, '_pattern_rows', v))

        # Square size
        square_label = QtWidgets.QLabel("Square size (mm):")
        self._square_spin = QtWidgets.QDoubleSpinBox()
        self._square_spin.setRange(1.0, 100.0)
        self._square_spin.setValue(self._square_mm)
        self._square_spin.setSuffix(" mm")
        self._square_spin.valueChanged.connect(lambda v: setattr(self, '_square_mm', v))

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(pattern_label)
        layout.addWidget(self._pattern_cols_spin)
        layout.addWidget(cross_label)
        layout.addWidget(self._pattern_rows_spin)
        layout.addWidget(QtWidgets.QLabel("  |  "))
        layout.addWidget(square_label)
        layout.addWidget(self._square_spin)
        layout.addStretch()

        group.setLayout(layout)
        return group

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
        # Open cameras if serials are set
        if self._left_serial and self._right_serial and not self._left_camera:
            self._open_cameras()

        # Start preview timer
        if self._left_camera and self._right_camera:
            self._preview_timer.start(33)  # ~30 FPS

    def on_exit(self) -> None:
        """Called when leaving step."""
        # Stop preview timer
        self._preview_timer.stop()

        # Close cameras
        self._close_cameras()

    def set_camera_serials(self, left_serial: str, right_serial: str) -> None:
        """Set camera serials from Step 1."""
        self._left_serial = left_serial
        self._right_serial = right_serial

    def _open_cameras(self) -> None:
        """Open camera devices."""
        try:
            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                # Extract index from "Camera N" format
                left_index = int(self._left_serial.split()[-1])
                right_index = int(self._right_serial.split()[-1])

                self._left_camera = OpenCVCamera(index=left_index)
                self._right_camera = OpenCVCamera(index=right_index)

            else:  # uvc
                from capture import UvcCamera

                self._left_camera = UvcCamera()
                self._right_camera = UvcCamera()

                # Open cameras with their serials
                self._left_camera.open(self._left_serial)
                self._right_camera.open(self._right_serial)

                # Configure cameras with basic settings
                self._left_camera.set_mode(640, 480, 120, "GRAY8")
                self._right_camera.set_mode(640, 480, 120, "GRAY8")

            # Start cameras
            self._left_camera.start()
            self._right_camera.start()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Camera Error",
                f"Failed to open cameras:\n{str(e)}",
            )

    def _close_cameras(self) -> None:
        """Close camera devices."""
        if self._left_camera:
            try:
                self._left_camera.stop()
                self._left_camera = None
            except Exception:
                pass

        if self._right_camera:
            try:
                self._right_camera.stop()
                self._right_camera = None
            except Exception:
                pass

    def _update_preview(self) -> None:
        """Update camera previews and check for checkerboard."""
        if not self._left_camera or not self._right_camera:
            return

        try:
            # Get frames
            left_frame = self._left_camera.read()
            right_frame = self._right_camera.read()

            if left_frame is None or right_frame is None:
                return

            # Check for checkerboard in both
            left_detected, left_image = self._detect_checkerboard(left_frame.image)
            right_detected, right_image = self._detect_checkerboard(right_frame.image)

            # Update previews
            self._update_view(self._left_view, left_image)
            self._update_view(self._right_view, right_image)

            # Update status indicators
            if left_detected:
                self._left_status.setText("● Checkerboard detected")
                self._left_status.setStyleSheet("color: green; font-weight: bold;")
            else:
                self._left_status.setText("● No checkerboard")
                self._left_status.setStyleSheet("color: red; font-weight: bold;")

            if right_detected:
                self._right_status.setText("● Checkerboard detected")
                self._right_status.setStyleSheet("color: green; font-weight: bold;")
            else:
                self._right_status.setText("● No checkerboard")
                self._right_status.setStyleSheet("color: red; font-weight: bold;")

            # Enable capture if both detected
            self._capture_button.setEnabled(left_detected and right_detected)

        except Exception:
            pass

    def _detect_checkerboard(self, image: np.ndarray) -> tuple[bool, np.ndarray]:
        """Detect checkerboard and draw corners.

        Returns:
            (detected, annotated_image)
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Find checkerboard corners
        pattern_size = (self._pattern_cols, self._pattern_rows)
        found, corners = cv2.findChessboardCorners(gray, pattern_size)

        # Draw corners if found
        annotated = image.copy()
        if found:
            cv2.drawChessboardCorners(annotated, pattern_size, corners, found)

        return found, annotated

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
            left_frame = self._left_camera.read()
            right_frame = self._right_camera.read()

            if left_frame is None or right_frame is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Capture Failed",
                    "Failed to read from cameras.",
                )
                return

            # Save to temp directory
            timestamp = int(time.time() * 1000)
            left_path = self._temp_dir / f"left_{timestamp}.png"
            right_path = self._temp_dir / f"right_{timestamp}.png"

            cv2.imwrite(str(left_path), left_frame.image)
            cv2.imwrite(str(right_path), right_frame.image)

            # Store capture
            self._captures.append((left_frame.image, right_frame.image))

            # Update UI
            count = len(self._captures)
            self._capture_count_label.setText(f"Captured: {count}")

            # Enable calibrate button if enough captures
            if count >= self._min_captures:
                self._calibrate_button.setEnabled(True)

            # Visual feedback
            self._capture_button.setStyleSheet("background-color: #4CAF50; color: white;")
            QtCore.QTimer.singleShot(200, lambda: self._capture_button.setStyleSheet(""))

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Capture Error",
                f"Failed to capture image pair:\n{str(e)}",
            )

    def _run_calibration(self) -> None:
        """Run stereo calibration on captured images."""
        if len(self._captures) < self._min_captures:
            QtWidgets.QMessageBox.warning(
                self,
                "Insufficient Captures",
                f"Need at least {self._min_captures} captures. Currently have {len(self._captures)}.",
            )
            return

        try:
            # Show progress
            self._results_text.setText("Calibrating... This may take a moment.")
            self._results_text.show()
            QtWidgets.QApplication.processEvents()

            # Get image paths
            left_paths = sorted(self._temp_dir.glob("left_*.png"))
            right_paths = sorted(self._temp_dir.glob("right_*.png"))

            # Run calibration
            pattern = f"{self._pattern_cols}x{self._pattern_rows}"
            result = calibrate_and_write(
                left_paths,
                right_paths,
                pattern,
                self._square_mm,
                self._config_path,
            )

            self._calibration_result = result

            # Show results
            results_text = (
                "✅ Calibration Complete!\n\n"
                f"Baseline: {result['baseline_ft']:.3f} ft\n"
                f"Focal Length: {result['focal_length_px']:.1f} px\n"
                f"Principal Point: ({result['cx']:.1f}, {result['cy']:.1f})\n\n"
                f"Calibration saved to {self._config_path}"
            )
            self._results_text.setText(results_text)
            self._results_text.setStyleSheet("background-color: #c8e6c9; color: #2e7d32;")

            QtWidgets.QMessageBox.information(
                self,
                "Calibration Complete",
                "Stereo calibration completed successfully!\n\n"
                "You can now proceed to the next step.",
            )

        except Exception as e:
            self._results_text.setText(f"❌ Calibration Failed:\n{str(e)}")
            self._results_text.setStyleSheet("background-color: #ffcdd2; color: #c62828;")

            QtWidgets.QMessageBox.critical(
                self,
                "Calibration Error",
                f"Calibration failed:\n{str(e)}",
            )
