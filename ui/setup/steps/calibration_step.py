"""Step 2: Stereo Calibration - Capture checkerboard images and calibrate."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, List

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from calib.quick_calibrate import calibrate_and_write
from capture import CameraDevice
from ui.setup.steps.base_step import BaseStep


class CalibrationWorker(QtCore.QThread):
    """Background worker for running calibration."""

    finished = QtCore.Signal(dict)  # Emits calibration results
    error = QtCore.Signal(str)  # Emits error message

    def __init__(
        self,
        left_paths: List[Path],
        right_paths: List[Path],
        pattern: str,
        square_mm: float,
        config_path: Path,
    ):
        super().__init__()
        self.left_paths = left_paths
        self.right_paths = right_paths
        self.pattern = pattern
        self.square_mm = square_mm
        self.config_path = config_path

    def run(self):
        """Run calibration in background thread."""
        try:
            result = calibrate_and_write(
                self.left_paths,
                self.right_paths,
                self.pattern,
                self.square_mm,
                self.config_path,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


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
        self._pattern_cols = 8
        self._pattern_rows = 6
        self._square_mm = 30.0  # 30mm square size
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
            "<b style='font-size: 12pt;'>Stereo Calibration - Need 10+ Image Pairs</b><br><br>"
            "<b>1.</b> Position checkerboard in the overlapping field of view between both cameras<br>"
            "<b>2.</b> Board can be distant/small - it doesn't need to fill the frame<br>"
            "<b>3.</b> When BOTH indicators turn <b>GREEN</b>, click <b>'Capture'</b><br>"
            "<b>4.</b> Move board to different positions, angles, and depths (near/far)<br>"
            "<b>5.</b> Capture at least 10 poses covering the tracking volume<br>"
            "<b>6.</b> More captures (15-20) = better calibration accuracy<br>"
            "<b>7.</b> Click <b>'Calibrate'</b> when you have 10+ captures"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "font-size: 10pt; padding: 12px; "
            "background-color: white; "
            "border: 2px solid #4CAF50; "
            "border-radius: 5px; "
            "color: black;"
        )
        layout.addWidget(instructions)

        # Settings row
        settings_group = self._build_settings_group()
        layout.addWidget(settings_group)

        # Pattern info
        self._pattern_info = QtWidgets.QLabel()
        self._pattern_info.setWordWrap(True)
        self._pattern_info.setStyleSheet(
            "color: black; "
            "background-color: #FFF9C4; "
            "padding: 8px; "
            "border: 1px solid #F57F17; "
            "border-radius: 4px; "
            "font-weight: bold;"
        )
        self._update_pattern_info()
        layout.addWidget(self._pattern_info)

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

        # Release cameras button for when they get stuck
        self._release_button = QtWidgets.QPushButton("🔓 Force Release Cameras")
        self._release_button.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
        self._release_button.clicked.connect(self._force_release_cameras)

        self._capture_count_label = QtWidgets.QLabel("Captured: 0 / 10 minimum")
        self._capture_count_label.setStyleSheet(
            "font-size: 14pt; "
            "font-weight: bold; "
            "color: #d32f2f; "
            "padding: 5px;"
        )

        self._calibrate_button = QtWidgets.QPushButton("🔧 Calibrate")
        self._calibrate_button.setMinimumHeight(40)
        self._calibrate_button.setEnabled(False)
        self._calibrate_button.clicked.connect(self._run_calibration)

        controls_layout.addWidget(self._capture_button, 2)
        controls_layout.addWidget(self._capture_count_label, 1)
        controls_layout.addWidget(self._calibrate_button, 2)
        layout.addLayout(controls_layout)

        # Release button in separate row for emergencies
        release_layout = QtWidgets.QHBoxLayout()
        release_layout.addStretch()
        release_layout.addWidget(self._release_button)
        release_layout.addStretch()
        layout.addLayout(release_layout)

        # Progress bar for calibration
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(0)  # Indeterminate mode
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Calibrating stereo cameras...")
        self._progress_bar.setStyleSheet(
            "QProgressBar {"
            "    border: 2px solid #2196F3;"
            "    border-radius: 5px;"
            "    text-align: center;"
            "    font-weight: bold;"
            "    font-size: 11pt;"
            "}"
            "QProgressBar::chunk {"
            "    background-color: #2196F3;"
            "    width: 20px;"
            "}"
        )
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # Results display
        self._results_text = QtWidgets.QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setMaximumHeight(100)
        self._results_text.hide()
        layout.addWidget(self._results_text)

        self.setLayout(layout)

    def _build_settings_group(self) -> QtWidgets.QWidget:
        """Build calibration settings groups."""
        container = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()

        # Checkerboard settings
        board_group = QtWidgets.QGroupBox("Checkerboard Settings")
        board_layout = QtWidgets.QHBoxLayout()

        # Pattern size
        pattern_label = QtWidgets.QLabel("Pattern (cols x rows):")
        self._pattern_cols_spin = QtWidgets.QSpinBox()
        self._pattern_cols_spin.setRange(3, 20)
        self._pattern_cols_spin.setValue(self._pattern_cols)
        self._pattern_cols_spin.valueChanged.connect(self._on_pattern_changed)

        cross_label = QtWidgets.QLabel("×")

        self._pattern_rows_spin = QtWidgets.QSpinBox()
        self._pattern_rows_spin.setRange(3, 20)
        self._pattern_rows_spin.setValue(self._pattern_rows)
        self._pattern_rows_spin.valueChanged.connect(self._on_pattern_changed)

        # Square size
        square_label = QtWidgets.QLabel("Square size (mm):")
        self._square_spin = QtWidgets.QDoubleSpinBox()
        self._square_spin.setRange(1.0, 100.0)
        self._square_spin.setValue(self._square_mm)
        self._square_spin.setSuffix(" mm")
        self._square_spin.valueChanged.connect(lambda v: setattr(self, '_square_mm', v))

        board_layout.addWidget(pattern_label)
        board_layout.addWidget(self._pattern_cols_spin)
        board_layout.addWidget(cross_label)
        board_layout.addWidget(self._pattern_rows_spin)
        board_layout.addWidget(QtWidgets.QLabel("  |  "))
        board_layout.addWidget(square_label)
        board_layout.addWidget(self._square_spin)
        board_layout.addStretch()
        board_group.setLayout(board_layout)

        # Camera & Stereo settings
        camera_group = QtWidgets.QGroupBox("Camera & Stereo Configuration")
        camera_layout = QtWidgets.QHBoxLayout()

        # Camera flip buttons
        flip_label = QtWidgets.QLabel("Flip Cameras:")
        self._flip_left_btn = QtWidgets.QPushButton("⟲ Flip Left 180°")
        self._flip_right_btn = QtWidgets.QPushButton("⟲ Flip Right 180°")
        self._flip_left_btn.setCheckable(True)
        self._flip_right_btn.setCheckable(True)

        # Load current flip state from config
        import yaml
        try:
            config_data = yaml.safe_load(self._config_path.read_text())
            self._flip_left_btn.setChecked(config_data.get("camera", {}).get("flip_left", False))
            self._flip_right_btn.setChecked(config_data.get("camera", {}).get("flip_right", False))
        except Exception:
            pass

        self._flip_left_btn.clicked.connect(lambda checked: self._toggle_flip("left", checked))
        self._flip_right_btn.clicked.connect(lambda checked: self._toggle_flip("right", checked))

        # Swap L/R button
        self._swap_lr_btn = QtWidgets.QPushButton("🔄 Swap L/R")
        self._swap_lr_btn.setToolTip("Swap left and right camera assignments")
        self._swap_lr_btn.clicked.connect(self._swap_left_right)
        self._swap_lr_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 5px 10px; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )

        # Baseline setting
        baseline_label = QtWidgets.QLabel("Baseline:")
        self._baseline_spin = QtWidgets.QDoubleSpinBox()
        self._baseline_spin.setRange(0.5, 10.0)
        self._baseline_spin.setSingleStep(0.125)  # 1.5 inch increments
        self._baseline_spin.setDecimals(3)
        self._baseline_spin.setSuffix(" ft")

        # Load current baseline from config
        try:
            baseline_ft = config_data.get("stereo", {}).get("baseline_ft", 1.625)
            self._baseline_spin.setValue(baseline_ft)
        except Exception:
            self._baseline_spin.setValue(1.625)

        self._baseline_spin.valueChanged.connect(self._update_baseline)

        # Baseline inches label
        baseline_inches = self._baseline_spin.value() * 12
        self._baseline_inches_label = QtWidgets.QLabel(f"({baseline_inches:.1f} in)")
        self._baseline_inches_label.setStyleSheet("color: #666; font-style: italic;")

        camera_layout.addWidget(flip_label)
        camera_layout.addWidget(self._flip_left_btn)
        camera_layout.addWidget(self._flip_right_btn)
        camera_layout.addWidget(self._swap_lr_btn)
        camera_layout.addWidget(QtWidgets.QLabel("  |  "))
        camera_layout.addWidget(baseline_label)
        camera_layout.addWidget(self._baseline_spin)
        camera_layout.addWidget(self._baseline_inches_label)
        camera_layout.addStretch()
        camera_group.setLayout(camera_layout)

        main_layout.addWidget(board_group)
        main_layout.addWidget(camera_group)
        container.setLayout(main_layout)
        return container

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
        # Clear any old calibration images from temp directory
        self._clear_temp_images()

        # Reset capture state
        self._captures.clear()
        self._capture_count_label.setText(f"Captured: 0 / {self._min_captures} minimum")
        self._capture_count_label.setStyleSheet(
            "font-size: 14pt; font-weight: bold; color: #d32f2f; padding: 5px;"
        )
        self._calibrate_button.setEnabled(False)

        # Close any existing cameras first to release resources
        if self._left_camera or self._right_camera:
            self._close_cameras()
            # Give Windows time to release camera handles
            time.sleep(0.5)

        # Open cameras if serials are set
        if self._left_serial and self._right_serial:
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

    def _on_pattern_changed(self, value: int) -> None:
        """Handle pattern size change."""
        self._pattern_cols = self._pattern_cols_spin.value()
        self._pattern_rows = self._pattern_rows_spin.value()
        self._update_pattern_info()

    def _update_pattern_info(self) -> None:
        """Update the pattern info label."""
        self._pattern_info.setText(
            f"<b>Looking for:</b> {self._pattern_cols}x{self._pattern_rows} checkerboard (internal corners). "
            f"<b>Stereo tip:</b> Board doesn't need to fill frame - move it to different positions "
            f"and angles in the shared view area between cameras. Capture 10+ poses for good calibration."
        )

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
        else:
            data["camera"]["flip_right"] = checked

        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Show feedback message
        orientation = "flipped 180°" if checked else "normal"
        print(f"INFO: {camera.capitalize()} camera {orientation} - restarting cameras...")

        # Restart cameras if open to apply flip
        if self._left_camera is not None or self._right_camera is not None:
            # Stop preview
            self._preview_timer.stop()

            # Close cameras
            self._close_cameras()

            # Reopen with new flip setting after short delay
            QtCore.QTimer.singleShot(300, self._restart_cameras_after_flip)

    def _restart_cameras_after_flip(self) -> None:
        """Reopen cameras and restart preview after flip setting change."""
        try:
            self._open_cameras()

            # Restart preview if cameras opened successfully
            if self._left_camera and self._right_camera:
                self._preview_timer.start(33)  # ~30 FPS
                print("INFO: Cameras restarted with new flip setting")
        except Exception as e:
            print(f"ERROR: Failed to restart cameras: {e}")

    def _swap_left_right(self) -> None:
        """Swap left and right camera assignments."""
        import yaml

        # Swap the serial numbers
        self._left_serial, self._right_serial = self._right_serial, self._left_serial

        print(f"INFO: Swapped cameras - Left: {self._left_serial}, Right: {self._right_serial}")

        # Swap flip button states (flip settings follow the camera, not the position)
        config_data = yaml.safe_load(self._config_path.read_text())
        flip_left = config_data.get("camera", {}).get("flip_left", False)
        flip_right = config_data.get("camera", {}).get("flip_right", False)

        # Update config with swapped flip states
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("camera", {})
        data["camera"]["flip_left"] = flip_right
        data["camera"]["flip_right"] = flip_left
        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Update button states to reflect swapped config
        self._flip_left_btn.setChecked(flip_right)
        self._flip_right_btn.setChecked(flip_left)

        # Restart cameras if open to apply swap
        if self._left_camera is not None or self._right_camera is not None:
            # Stop preview
            self._preview_timer.stop()

            # Close cameras
            self._close_cameras()

            # Reopen with swapped assignments after short delay
            QtCore.QTimer.singleShot(300, self._restart_cameras_after_swap)

    def _restart_cameras_after_swap(self) -> None:
        """Reopen cameras and restart preview after L/R swap."""
        try:
            self._open_cameras()

            # Restart preview if cameras opened successfully
            if self._left_camera and self._right_camera:
                self._preview_timer.start(33)  # ~30 FPS
                print("INFO: Cameras restarted with swapped L/R assignment")
        except Exception as e:
            print(f"ERROR: Failed to restart cameras after swap: {e}")

    def _update_baseline(self, value_ft: float) -> None:
        """Update baseline distance in config.

        Args:
            value_ft: Baseline distance in feet
        """
        import yaml

        # Update config file
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("stereo", {})
        data["stereo"]["baseline_ft"] = float(value_ft)
        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Update inches label
        baseline_inches = value_ft * 12
        if hasattr(self, "_baseline_inches_label"):
            self._baseline_inches_label.setText(f"({baseline_inches:.1f} in)")

    def _clear_temp_images(self) -> None:
        """Clear old calibration images from temp directory."""
        import shutil

        if self._temp_dir.exists():
            # Remove all files in temp directory
            for file in self._temp_dir.glob("*.png"):
                try:
                    file.unlink()
                except Exception:
                    pass
        else:
            # Create temp directory if it doesn't exist
            self._temp_dir.mkdir(parents=True, exist_ok=True)

    def _open_cameras(self) -> None:
        """Open camera devices."""
        try:
            if not self._left_serial or not self._right_serial:
                raise ValueError("Camera serials not set. Please select cameras in Step 1.")

            # Read flip settings from config
            import yaml
            config_data = yaml.safe_load(self._config_path.read_text())
            flip_left = config_data.get("camera", {}).get("flip_left", False)
            flip_right = config_data.get("camera", {}).get("flip_right", False)

            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                # Extract index from "Camera N" format or use serial directly if it's a number
                if self._left_serial.isdigit():
                    left_index = self._left_serial
                else:
                    left_index = self._left_serial.split()[-1]

                if self._right_serial.isdigit():
                    right_index = self._right_serial
                else:
                    right_index = self._right_serial.split()[-1]

                self._left_camera = OpenCVCamera()
                self._right_camera = OpenCVCamera()

                print(f"DEBUG: Opening left camera with index: {left_index} (flip={flip_left})")
                self._left_camera.open(left_index)

                print(f"DEBUG: Opening right camera with index: {right_index} (flip={flip_right})")
                self._right_camera.open(right_index)

                # Configure cameras with basic settings including flip
                self._left_camera.set_mode(640, 480, 30, "GRAY8", flip_180=flip_left)
                self._right_camera.set_mode(640, 480, 30, "GRAY8", flip_180=flip_right)

            else:  # uvc
                from capture import UvcCamera

                self._left_camera = UvcCamera()
                self._right_camera = UvcCamera()

                # Open cameras with their serials - retry with delays if needed
                print(f"DEBUG: Opening left camera with serial: {self._left_serial} (flip={flip_left})")
                for attempt in range(3):
                    try:
                        self._left_camera.open(self._left_serial)
                        break
                    except Exception as e:
                        if attempt < 2:
                            print(f"DEBUG: Left camera open attempt {attempt + 1} failed, retrying...")
                            time.sleep(1.0)
                        else:
                            raise

                print(f"DEBUG: Opening right camera with serial: {self._right_serial} (flip={flip_right})")
                for attempt in range(3):
                    try:
                        self._right_camera.open(self._right_serial)
                        break
                    except Exception as e:
                        if attempt < 2:
                            print(f"DEBUG: Right camera open attempt {attempt + 1} failed, retrying...")
                            time.sleep(1.0)
                        else:
                            raise

                # Configure cameras with basic settings including flip
                self._left_camera.set_mode(640, 480, 30, "GRAY8", flip_180=flip_left)
                self._right_camera.set_mode(640, 480, 30, "GRAY8", flip_180=flip_right)

            # Update status labels to show which camera is assigned to which position
            self._left_status.setText(f"● {self._left_serial}")
            self._left_status.setStyleSheet("color: green; font-weight: bold;")
            self._right_status.setText(f"● {self._right_serial}")
            self._right_status.setStyleSheet("color: green; font-weight: bold;")

        except Exception as e:
            # Clean up any partially opened cameras
            self._close_cameras()

            error_msg = (
                f"Failed to open cameras:\n{str(e)}\n\n"
                f"Left Camera: {self._left_serial}\n"
                f"Right Camera: {self._right_serial}\n\n"
                "Common causes:\n"
                "• Cameras are in use by another application (close other apps)\n"
                "• Cameras were not properly released (try going back to Step 1)\n"
                "• Incorrect permissions or driver issues\n"
                "• Cameras disconnected"
            )

            QtWidgets.QMessageBox.critical(
                self,
                "Camera Error",
                error_msg,
            )

    def _close_cameras(self) -> None:
        """Close camera devices."""
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

        # Reset status labels
        self._left_status.setText("● Waiting...")
        self._left_status.setStyleSheet("color: gray; font-weight: bold;")
        self._right_status.setText("● Waiting...")
        self._right_status.setStyleSheet("color: gray; font-weight: bold;")

        # Force garbage collection to release any lingering handles
        import gc
        gc.collect()

    def _force_release_cameras(self) -> None:
        """Aggressively release camera resources (for when cameras get stuck)."""
        import gc
        import cv2

        # Stop preview timer first
        self._preview_timer.stop()

        # Try normal close
        self._close_cameras()

        # Get list of camera device names
        from capture.uvc_backend import list_uvc_devices
        devices = list_uvc_devices()

        # Build list of device friendly names to try
        device_names = []
        for device in devices:
            serial = device.get("serial", "")
            friendly = device.get("friendly_name", "")
            if serial in [self._left_serial, self._right_serial]:
                device_names.append(friendly)

        # Try to open and immediately close using cv2 directly to force DirectShow release
        for device_name in device_names:
            for attempt in range(3):
                cap = None
                try:
                    # Try to open with DirectShow
                    cap = cv2.VideoCapture(f"video={device_name}", cv2.CAP_DSHOW)
                    if cap.isOpened():
                        cap.read()  # Try to read one frame
                except Exception:
                    pass
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
                    del cap

                time.sleep(0.3)
                gc.collect()

        # Final aggressive cleanup
        time.sleep(1.0)
        gc.collect()

        QtWidgets.QMessageBox.information(
            self,
            "Cameras Released",
            "Camera resources have been forcibly released.\n\n"
            "You can now try opening the cameras again by going back to Step 1 "
            "and then returning to Step 2.",
        )

    def _update_preview(self) -> None:
        """Update camera previews and check for checkerboard."""
        if not self._left_camera or not self._right_camera:
            return

        try:
            # Get frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

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
        # Convert to grayscale for detection
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Find checkerboard corners with multiple strategies
        pattern_size = (self._pattern_cols, self._pattern_rows)
        found = False
        corners = None

        # Strategy 1: Fast check with adaptive threshold (fastest, good for clear images)
        flags = (
            cv2.CALIB_CB_ADAPTIVE_THRESH +
            cv2.CALIB_CB_NORMALIZE_IMAGE +
            cv2.CALIB_CB_FAST_CHECK
        )
        found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)

        # Strategy 2: Without fast check (slower, more thorough)
        if not found:
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)

        # Strategy 3: With filtering for distant/small boards
        if not found:
            flags = (
                cv2.CALIB_CB_ADAPTIVE_THRESH +
                cv2.CALIB_CB_NORMALIZE_IMAGE +
                cv2.CALIB_CB_FILTER_QUADS
            )
            found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)

        # Prepare annotated image - convert to BGR if grayscale for drawing
        if len(image.shape) == 2:
            annotated = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            annotated = image.copy()

        # Draw corners if found
        if found and corners is not None:
            # Refine corner positions for better accuracy
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            cv2.drawChessboardCorners(annotated, pattern_size, corners_refined, found)
        else:
            # Draw hint text when not detected
            hint_text = f"Move {self._pattern_cols}x{self._pattern_rows} board into shared view"
            cv2.putText(
                annotated,
                hint_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

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
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

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
            if count < self._min_captures:
                self._capture_count_label.setText(f"Captured: {count} / {self._min_captures} minimum")
                self._capture_count_label.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; color: #d32f2f; padding: 5px;"
                )
            else:
                self._capture_count_label.setText(f"Captured: {count} ✓ (Ready to calibrate)")
                self._capture_count_label.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; color: #388e3c; padding: 5px;"
                )

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
        self._calibration_worker = CalibrationWorker(
            left_paths,
            right_paths,
            pattern,
            self._square_mm,
            self._config_path,
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
        results_text = (
            f"{emoji} Calibration {rating}!\n\n"
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

        # Color code based on quality
        if rating in ['EXCELLENT', 'GOOD']:
            bg_color = "#c8e6c9"  # Green
            text_color = "#2e7d32"
        elif rating == 'ACCEPTABLE':
            bg_color = "#fff9c4"  # Yellow
            text_color = "#f57f17"
        else:  # POOR
            bg_color = "#ffcdd2"  # Red
            text_color = "#c62828"

        self._results_text.setText(results_text)
        self._results_text.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; "
            f"padding: 12px; border-radius: 4px; font-family: monospace;"
        )
        self._results_text.show()

        # Re-enable buttons
        self._capture_button.setEnabled(True)
        self._calibrate_button.setEnabled(True)

        # Show appropriate message dialog based on quality
        if rating == 'POOR':
            QtWidgets.QMessageBox.warning(
                self,
                "Poor Calibration Quality",
                f"Calibration quality is poor (RMS error: {rms_error:.2f} px).\n\n"
                f"We strongly recommend recalibrating:\n\n"
                + "\n".join(recommendations),
                QtWidgets.QMessageBox.Ok
            )
        elif rating in ['EXCELLENT', 'GOOD']:
            QtWidgets.QMessageBox.information(
                self,
                "Calibration Complete",
                f"Stereo calibration completed with {rating} quality!\n\n"
                f"Reprojection error: {rms_error:.3f} px\n\n"
                "You can now proceed to the next step.",
            )
        else:  # ACCEPTABLE
            QtWidgets.QMessageBox.information(
                self,
                "Calibration Complete",
                f"Stereo calibration completed with acceptable quality.\n\n"
                f"Reprojection error: {rms_error:.3f} px\n\n"
                "You can proceed, but consider recalibrating with more images for better accuracy.",
            )

    def _on_calibration_error(self, error_msg: str) -> None:
        """Handle calibration error."""
        # Hide progress bar
        self._progress_bar.hide()

        # Show error
        self._results_text.setText(f"❌ Calibration Failed:\n{error_msg}")
        self._results_text.setStyleSheet("background-color: #ffcdd2; color: #c62828;")
        self._results_text.show()

        # Re-enable buttons
        self._capture_button.setEnabled(True)
        self._calibrate_button.setEnabled(True)

        QtWidgets.QMessageBox.critical(
            self,
            "Calibration Error",
            f"Calibration failed:\n{error_msg}",
        )
