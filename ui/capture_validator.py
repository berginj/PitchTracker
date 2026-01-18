"""Camera Capture Validator - Simple tool to test calibrated cameras.

This application validates camera setup and calibration by:
- Loading calibration settings
- Showing live preview from both cameras
- Recording raw video for testing
- No detection or tracking pipeline

Use this to verify cameras are working correctly before running full sessions.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import cv2
from PySide6 import QtCore, QtGui, QtWidgets

from capture import CameraDevice
from configs.settings import AppConfig, load_config

logger = logging.getLogger(__name__)


class CaptureValidatorWindow(QtWidgets.QMainWindow):
    """Simple camera capture validator for testing calibrated cameras."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        backend: str = "opencv",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Camera Capture Validator")
        self.resize(1200, 700)

        # Load configuration
        if config_path is None:
            config_path = Path("configs/default.yaml")
        self._config_path = config_path
        self._config = load_config(config_path)
        self._backend = backend

        # Cameras
        self._left_camera: Optional[CameraDevice] = None
        self._right_camera: Optional[CameraDevice] = None
        self._left_serial: Optional[str] = None
        self._right_serial: Optional[str] = None

        # Video writers
        self._left_writer: Optional[cv2.VideoWriter] = None
        self._right_writer: Optional[cv2.VideoWriter] = None
        self._recording = False
        self._test_dir: Optional[Path] = None

        # Build UI
        self._build_ui()

        # Preview timer
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)

    def _build_ui(self) -> None:
        """Build validator UI."""
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("Camera Capture Validator")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        info = QtWidgets.QLabel(
            "Test your calibrated cameras by viewing live preview and recording raw video.\n"
            "No detection or tracking - just camera capture validation."
        )
        info.setStyleSheet("padding: 5px; color: #666; font-style: italic;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Camera previews
        preview_layout = QtWidgets.QHBoxLayout()

        # Left camera
        left_group = QtWidgets.QGroupBox("Left Camera")
        self._left_view = QtWidgets.QLabel("No preview")
        self._left_view.setMinimumSize(500, 375)
        self._left_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_view.setStyleSheet("background-color: #000000; color: #ffffff;")
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._left_view)
        left_group.setLayout(left_layout)
        preview_layout.addWidget(left_group)

        # Right camera
        right_group = QtWidgets.QGroupBox("Right Camera")
        self._right_view = QtWidgets.QLabel("No preview")
        self._right_view.setMinimumSize(500, 375)
        self._right_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_view.setStyleSheet("background-color: #000000; color: #ffffff;")
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self._right_view)
        right_group.setLayout(right_layout)
        preview_layout.addWidget(right_group)

        layout.addLayout(preview_layout, 1)

        # Controls
        controls_layout = QtWidgets.QHBoxLayout()

        self._start_button = QtWidgets.QPushButton("▶ Start Cameras")
        self._start_button.setMinimumHeight(50)
        self._start_button.setStyleSheet("font-size: 14pt; background-color: #4CAF50; color: white;")
        self._start_button.clicked.connect(self._start_cameras)

        self._record_button = QtWidgets.QPushButton("⏺ Start Recording")
        self._record_button.setMinimumHeight(50)
        self._record_button.setStyleSheet("font-size: 14pt; background-color: #f44336; color: white;")
        self._record_button.setEnabled(False)
        self._record_button.clicked.connect(self._toggle_recording)

        self._stop_button = QtWidgets.QPushButton("⏹ Stop Cameras")
        self._stop_button.setMinimumHeight(50)
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self._stop_cameras)

        controls_layout.addWidget(self._start_button, 2)
        controls_layout.addWidget(self._record_button, 2)
        controls_layout.addWidget(self._stop_button, 1)
        layout.addLayout(controls_layout)

        # Status
        self._status_label = QtWidgets.QLabel("Ready. Click 'Start Cameras' to begin.")
        self._status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")
        layout.addWidget(self._status_label)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _start_cameras(self) -> None:
        """Start camera capture."""
        # Get camera serials from app state
        from configs.app_state import load_state
        state = load_state()
        self._left_serial = state.get("last_left_camera", "0")
        self._right_serial = state.get("last_right_camera", "1")

        try:
            self._status_label.setText("Starting cameras...")
            QtWidgets.QApplication.processEvents()

            # Open cameras
            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                self._left_camera = OpenCVCamera()
                self._left_camera.open(self._left_serial)
                # Use lower resolution for validator
                self._left_camera.set_mode(640, 480, 30, "GRAY8")

                self._right_camera = OpenCVCamera()
                self._right_camera.open(self._right_serial)
                self._right_camera.set_mode(640, 480, 30, "GRAY8")

            else:  # uvc
                from capture import UvcCamera

                self._left_camera = UvcCamera()
                self._left_camera.open(self._left_serial)
                self._left_camera.set_mode(640, 480, 30, "GRAY8")

                self._right_camera = UvcCamera()
                self._right_camera.open(self._right_serial)
                self._right_camera.set_mode(640, 480, 30, "GRAY8")

            # Start preview
            self._preview_timer.start(33)  # ~30 FPS

            # Update UI
            self._start_button.setEnabled(False)
            self._record_button.setEnabled(True)
            self._stop_button.setEnabled(True)
            self._status_label.setText(f"✓ Cameras running: Left={self._left_serial}, Right={self._right_serial}")
            self._status_label.setStyleSheet("padding: 5px; background-color: #c8e6c9; color: #2e7d32;")

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Camera Error",
                f"Failed to start cameras:\n{e}\n\nCheck camera connections and permissions.",
            )
            self._stop_cameras()

    def _stop_cameras(self) -> None:
        """Stop camera capture."""
        # Stop recording if active
        if self._recording:
            self._toggle_recording()

        # Stop preview
        self._preview_timer.stop()

        # Close cameras
        if self._left_camera:
            try:
                self._left_camera.stop()
                self._left_camera.close()
            except Exception:
                pass
            finally:
                self._left_camera = None

        if self._right_camera:
            try:
                self._right_camera.stop()
                self._right_camera.close()
            except Exception:
                pass
            finally:
                self._right_camera = None

        # Clear displays
        self._left_view.clear()
        self._left_view.setText("No preview")
        self._right_view.clear()
        self._right_view.setText("No preview")

        # Update UI
        self._start_button.setEnabled(True)
        self._record_button.setEnabled(False)
        self._stop_button.setEnabled(False)
        self._status_label.setText("Cameras stopped.")
        self._status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")

    def _toggle_recording(self) -> None:
        """Toggle video recording."""
        if not self._recording:
            # Start recording
            try:
                # Create test directory
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                self._test_dir = Path(f"camera_tests/test_{timestamp}")
                self._test_dir.mkdir(parents=True, exist_ok=True)

                # Create video writers
                fourcc = cv2.VideoWriter_fourcc(*"MJPG")

                left_path = self._test_dir / "left_camera.avi"
                self._left_writer = cv2.VideoWriter(
                    str(left_path),
                    fourcc,
                    30.0,
                    (640, 480),
                    False,  # Grayscale
                )

                # Fallback to XVID if MJPG fails
                if not self._left_writer.isOpened():
                    fourcc = cv2.VideoWriter_fourcc(*"XVID")
                    self._left_writer = cv2.VideoWriter(
                        str(left_path),
                        fourcc,
                        30.0,
                        (640, 480),
                        False,
                    )

                right_path = self._test_dir / "right_camera.avi"
                self._right_writer = cv2.VideoWriter(
                    str(right_path),
                    fourcc,
                    30.0,
                    (640, 480),
                    False,
                )

                # Save metadata
                metadata_path = self._test_dir / "test_info.txt"
                metadata_path.write_text(
                    f"Camera Test Recording\n"
                    f"Timestamp: {timestamp}\n"
                    f"Left Camera: {self._left_serial}\n"
                    f"Right Camera: {self._right_serial}\n"
                    f"Resolution: 640x480\n"
                    f"FPS: 30\n"
                    f"Backend: {self._backend}\n"
                )

                self._recording = True
                self._record_button.setText("⏹ Stop Recording")
                self._record_button.setStyleSheet("font-size: 14pt; background-color: #FF5722; color: white;")
                self._status_label.setText(f"⏺ Recording to: {self._test_dir}")
                self._status_label.setStyleSheet("padding: 5px; background-color: #ffcdd2; color: #c62828;")

            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Recording Error",
                    f"Failed to start recording:\n{e}",
                )

        else:
            # Stop recording
            if self._left_writer:
                self._left_writer.release()
                self._left_writer = None

            if self._right_writer:
                self._right_writer.release()
                self._right_writer = None

            self._recording = False
            self._record_button.setText("⏺ Start Recording")
            self._record_button.setStyleSheet("font-size: 14pt; background-color: #f44336; color: white;")
            self._status_label.setText(f"✓ Recording saved to: {self._test_dir}")
            self._status_label.setStyleSheet("padding: 5px; background-color: #c8e6c9; color: #2e7d32;")

            # Show directory
            QtWidgets.QMessageBox.information(
                self,
                "Recording Complete",
                f"Test recording saved to:\n{self._test_dir}\n\n"
                f"Files:\n"
                f"- left_camera.avi\n"
                f"- right_camera.avi\n"
                f"- test_info.txt",
            )

    def _update_preview(self) -> None:
        """Update camera preview frames."""
        if not self._left_camera or not self._right_camera:
            return

        try:
            # Get frames
            left_frame = self._left_camera.read_frame(timeout_ms=100)
            right_frame = self._right_camera.read_frame(timeout_ms=100)

            # Update left view
            if left_frame is not None:
                image = left_frame.image.copy()

                # Write to video if recording
                if self._recording and self._left_writer:
                    self._left_writer.write(image)

                # Add label to preview
                cv2.putText(
                    image,
                    f"LEFT: {self._left_serial}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )
                if self._recording:
                    cv2.circle(image, (620, 30), 10, (255, 255, 255), -1)

                pixmap = self._frame_to_pixmap(image)
                if pixmap:
                    scaled = pixmap.scaled(
                        self._left_view.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                    self._left_view.setPixmap(scaled)

            # Update right view
            if right_frame is not None:
                image = right_frame.image.copy()

                # Write to video if recording
                if self._recording and self._right_writer:
                    self._right_writer.write(image)

                # Add label to preview
                cv2.putText(
                    image,
                    f"RIGHT: {self._right_serial}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )
                if self._recording:
                    cv2.circle(image, (620, 30), 10, (255, 255, 255), -1)

                pixmap = self._frame_to_pixmap(image)
                if pixmap:
                    scaled = pixmap.scaled(
                        self._right_view.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                    self._right_view.setPixmap(scaled)

        except Exception as e:
            logger.error(f"Preview update failed: {e}")

    def _frame_to_pixmap(self, image) -> Optional[QtGui.QPixmap]:
        """Convert numpy image to QPixmap."""
        try:
            import numpy as np

            # Ensure image is uint8
            if image.dtype != np.uint8:
                image = image.astype(np.uint8)

            # Create QImage
            height, width = image.shape[:2]
            if len(image.shape) == 3:
                bytes_per_line = 3 * width
                q_image = QtGui.QImage(
                    image.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_RGB888,
                )
            else:
                bytes_per_line = width
                q_image = QtGui.QImage(
                    image.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_Grayscale8,
                )

            return QtGui.QPixmap.fromImage(q_image)

        except Exception as e:
            logger.warning(f"Failed to convert frame to pixmap: {e}")
            return None

    def closeEvent(self, event) -> None:
        """Handle window close."""
        self._stop_cameras()
        event.accept()
