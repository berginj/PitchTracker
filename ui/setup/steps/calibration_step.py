"""Step 2: Stereo Calibration - Capture ChArUco board images and calibrate."""

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
    """Step 2: Stereo calibration with ChArUco board pattern.

    Workflow:
    1. Show live preview from both cameras
    2. Detect ChArUco board in real-time (robust to partial occlusion)
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

        # Alignment history tracking
        self._alignment_history: list = []  # Track alignment iterations
        self._alignment_results: Optional = None  # Current alignment results
        self._baseline_alignment: Optional = None  # Baseline from first capture (drift detection)
        self._warmup_attempts: int = 0  # Camera warmup retry counter

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
            "<b>1.</b> Position ChArUco board in the overlapping field of view between both cameras<br>"
            "<b>2.</b> Board can be distant/small or partially visible - ChArUco is robust to occlusion<br>"
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

        # NEW: Alignment status widget (automatically populated after cameras open)
        self._alignment_widget = self._build_alignment_widget()
        layout.addWidget(self._alignment_widget)

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
        self._left_view.setMinimumSize(640, 480)  # Large preview for better visibility (960x600 expectation)
        self._left_view.setScaledContents(True)
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
        self._right_view.setMinimumSize(640, 480)  # Large preview for better visibility (960x600 expectation)
        self._right_view.setScaledContents(True)
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

        # Wrap entire layout in scroll area for accessibility
        scroll_content = QtWidgets.QWidget()
        scroll_content.setLayout(layout)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)

    def _build_settings_group(self) -> QtWidgets.QWidget:
        """Build calibration settings groups."""
        container = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()

        # ChArUco board settings
        board_group = QtWidgets.QGroupBox("ChArUco Board Settings")
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

        # Auto-correction checkbox
        self._auto_correct_checkbox = QtWidgets.QCheckBox("Auto-apply alignment corrections")
        self._auto_correct_checkbox.setChecked(False)  # OFF by default
        self._auto_correct_checkbox.setToolTip(
            "When enabled, automatically apply software corrections for camera rotation and vertical offset.\n"
            "When disabled, alignment is checked but corrections are NOT applied automatically.\n"
            "You can manually apply corrections using the alignment widget buttons.\n\n"
            "Recommendation: Keep OFF unless you understand the alignment diagnostics."
        )
        self._auto_correct_checkbox.setStyleSheet("font-weight: bold; color: #D32F2F;")  # Red to emphasize OFF default

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
        self._baseline_spin.setToolTip(
            "Camera spacing (lens center to lens center).\n"
            "Enter your measured value here.\n"
            "Calibration will refine this to a precise value."
        )

        # Load current baseline from config
        try:
            baseline_ft = config_data.get("stereo", {}).get("baseline_ft", 1.625)
            self._baseline_spin.setValue(baseline_ft)
        except Exception:
            self._baseline_spin.setValue(1.625)

        self._baseline_spin.valueChanged.connect(self._update_baseline)

        # Baseline status label (shows if manual or calibrated)
        # Check if this looks like a calibrated value (has many decimal places) or manual (round)
        is_calibrated = abs(baseline_ft - round(baseline_ft * 8) / 8) > 0.01  # Not a 1/8 ft increment
        baseline_inches = self._baseline_spin.value() * 12

        if is_calibrated:
            status_text = f"({baseline_inches:.1f} in) 📐 Calibrated"
            status_color = "#2196F3"  # Blue
            status_tip = "This value was calculated by stereo calibration (more accurate than manual measurement)"
        else:
            status_text = f"({baseline_inches:.1f} in) ✏️ Manual"
            status_color = "#FF9800"  # Orange
            status_tip = "This is a manually entered value. Run calibration to get a precise measurement."

        self._baseline_inches_label = QtWidgets.QLabel(status_text)
        self._baseline_inches_label.setStyleSheet(f"color: {status_color}; font-style: italic; font-weight: bold;")
        self._baseline_inches_label.setToolTip(status_tip)

        camera_layout.addWidget(flip_label)
        camera_layout.addWidget(self._flip_left_btn)
        camera_layout.addWidget(self._flip_right_btn)
        camera_layout.addWidget(self._swap_lr_btn)
        camera_layout.addWidget(QtWidgets.QLabel("  |  "))
        camera_layout.addWidget(self._auto_correct_checkbox)
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

    def _build_alignment_widget(self) -> QtWidgets.QGroupBox:
        """Build automatic camera alignment status widget.

        This widget is automatically populated after cameras open.
        Shows alignment quality and any corrections applied.
        """
        group = QtWidgets.QGroupBox("Camera Alignment Status")
        layout = QtWidgets.QVBoxLayout()

        # Status label (updated automatically) - wrapped in scroll area
        self._alignment_status_label = QtWidgets.QLabel("⏳ Checking alignment...")
        self._alignment_status_label.setWordWrap(True)
        self._alignment_status_label.setStyleSheet(
            "font-size: 10pt; padding: 8px; "
            "color: #000000; "  # Dark text for readability
            "background-color: #E3F2FD; "
            "border: 1px solid #2196F3; "
            "border-radius: 4px;"
        )

        # Wrap in scroll area to limit height
        status_scroll = QtWidgets.QScrollArea()
        status_scroll.setWidget(self._alignment_status_label)
        status_scroll.setWidgetResizable(True)
        status_scroll.setMaximumHeight(150)  # Limit to 150px
        status_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        status_scroll.setStyleSheet("background-color: transparent;")
        layout.addWidget(status_scroll)

        # NEW: Quality gauge (visual score indicator)
        self._quality_gauge = QtWidgets.QLabel()
        self._quality_gauge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._quality_gauge.setStyleSheet(
            "font-size: 11pt; font-weight: bold; padding: 12px; "
            "color: #000000; "  # Dark text for readability
            "background-color: #F5F5F5; "
            "border: 2px solid #E0E0E0; "
            "border-radius: 8px;"
        )
        self._quality_gauge.hide()
        layout.addWidget(self._quality_gauge)

        # Details (hidden by default, shown after check)
        self._alignment_details = QtWidgets.QLabel()
        self._alignment_details.setWordWrap(True)
        self._alignment_details.setStyleSheet(
            "font-size: 9pt; padding: 6px; color: #555;"
        )
        self._alignment_details.hide()
        layout.addWidget(self._alignment_details)

        # NEW: Directional Guidance (hidden by default)
        self._guidance_label = QtWidgets.QLabel()
        self._guidance_label.setWordWrap(True)
        self._guidance_label.setStyleSheet(
            "font-size: 9pt; padding: 8px; "
            "background-color: #FFF9C4; "
            "border: 1px solid #FBC02D; "
            "border-radius: 4px;"
        )
        self._guidance_label.hide()
        layout.addWidget(self._guidance_label)

        # NEW: Predicted Calibration Quality (hidden by default)
        self._prediction_label = QtWidgets.QLabel()
        self._prediction_label.setWordWrap(True)
        self._prediction_label.setStyleSheet(
            "font-size: 9pt; padding: 8px; "
            "background-color: #E8F5E9; "
            "border: 1px solid #4CAF50; "
            "border-radius: 4px;"
        )
        self._prediction_label.hide()
        layout.addWidget(self._prediction_label)

        # NEW: Alignment History (collapsible, hidden by default)
        self._history_group = QtWidgets.QGroupBox("Alignment History")
        self._history_group.setCheckable(True)
        self._history_group.setChecked(False)  # Collapsed by default
        history_layout = QtWidgets.QVBoxLayout()

        self._history_list = QtWidgets.QTextEdit()
        self._history_list.setReadOnly(True)
        self._history_list.setMaximumHeight(150)
        self._history_list.setStyleSheet("font-family: monospace; font-size: 9pt;")
        history_layout.addWidget(self._history_list)

        self._history_group.setLayout(history_layout)
        self._history_group.hide()
        layout.addWidget(self._history_group)

        # Buttons row (hidden by default)
        buttons_layout = QtWidgets.QHBoxLayout()

        self._recheck_alignment_btn = QtWidgets.QPushButton("🔄 Full Check")
        self._recheck_alignment_btn.setToolTip("Run full alignment check (averaged over 10 frames, ~1 second)")
        self._recheck_alignment_btn.clicked.connect(self._run_automatic_alignment_check)
        self._recheck_alignment_btn.hide()

        self._quick_check_btn = QtWidgets.QPushButton("⚡ Quick Check")
        self._quick_check_btn.setToolTip("Run quick alignment check (1 frame, <100ms)")
        self._quick_check_btn.clicked.connect(self._run_quick_alignment_check)
        self._quick_check_btn.hide()

        self._alignment_details_btn = QtWidgets.QPushButton("📊 Details")
        self._alignment_details_btn.setToolTip("Show detailed alignment report")
        self._alignment_details_btn.clicked.connect(self._show_alignment_details)
        self._alignment_details_btn.hide()

        self._show_features_btn = QtWidgets.QPushButton("👁 Show Features")
        self._show_features_btn.setToolTip("Visualize matched features on camera previews")
        self._show_features_btn.clicked.connect(self._show_feature_overlay)
        self._show_features_btn.hide()

        self._export_report_btn = QtWidgets.QPushButton("📄 Export Report")
        self._export_report_btn.setToolTip("Export alignment report as HTML")
        self._export_report_btn.clicked.connect(self._export_alignment_report)
        self._export_report_btn.hide()

        buttons_layout.addWidget(self._recheck_alignment_btn)
        buttons_layout.addWidget(self._quick_check_btn)
        buttons_layout.addWidget(self._alignment_details_btn)
        buttons_layout.addWidget(self._show_features_btn)
        buttons_layout.addWidget(self._export_report_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # NEW: Preset management buttons (second row)
        preset_layout = QtWidgets.QHBoxLayout()

        self._save_preset_btn = QtWidgets.QPushButton("💾 Save Preset")
        self._save_preset_btn.setToolTip("Save current alignment as a preset")
        self._save_preset_btn.clicked.connect(self._save_alignment_preset)
        self._save_preset_btn.hide()

        self._load_preset_btn = QtWidgets.QPushButton("📂 Load Preset")
        self._load_preset_btn.setToolTip("Load a saved alignment preset")
        self._load_preset_btn.clicked.connect(self._load_alignment_preset)
        self._load_preset_btn.hide()

        self._compare_preset_btn = QtWidgets.QPushButton("⚖️ Compare")
        self._compare_preset_btn.setToolTip("Compare current alignment with saved preset")
        self._compare_preset_btn.clicked.connect(self._compare_with_preset)
        self._compare_preset_btn.hide()

        preset_layout.addWidget(self._save_preset_btn)
        preset_layout.addWidget(self._load_preset_btn)
        preset_layout.addWidget(self._compare_preset_btn)
        preset_layout.addStretch()
        layout.addLayout(preset_layout)

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
        # Clear any old calibration images from temp directory
        self._clear_temp_images()

        # Reset capture state
        self._captures.clear()
        self._baseline_alignment = None  # Reset drift detection baseline
        self._warmup_attempts = 0  # Reset warmup counter
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

        # Load previous alignment history
        self._load_alignment_history()

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
            f"<b>Looking for:</b> {self._pattern_cols}x{self._pattern_rows} ChArUco board (squares with ArUco markers). "
            f"<b>Stereo tip:</b> Board can be partially visible - ChArUco is robust to occlusion. "
            f"Move it to different positions and angles in the shared view area. Capture 10+ poses for good calibration."
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
            # Clear rotation correction since alignment will be rechecked after flip
            data["camera"]["rotation_left"] = 0.0
        else:
            data["camera"]["flip_right"] = checked
            # Clear rotation correction since alignment will be rechecked after flip
            data["camera"]["rotation_right"] = 0.0

        # Also clear vertical offset since camera orientation changed
        data["camera"]["vertical_offset_px"] = 0

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

        # Update inches label and status
        baseline_inches = value_ft * 12
        if hasattr(self, "_baseline_inches_label"):
            # User is manually entering, so mark as manual (orange)
            self._baseline_inches_label.setText(f"({baseline_inches:.1f} in) ✏️ Manual")
            self._baseline_inches_label.setStyleSheet("color: #FF9800; font-style: italic; font-weight: bold;")
            self._baseline_inches_label.setToolTip(
                "This is a manually entered value. Run calibration to get a precise measurement."
            )

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

            # Read camera settings from config
            import yaml
            config_data = yaml.safe_load(self._config_path.read_text())

            # Resolution and framerate from config
            camera_config = config_data.get("camera", {})
            width = camera_config.get("width", 1280)
            height = camera_config.get("height", 720)
            fps = camera_config.get("fps", 60)
            pixfmt = camera_config.get("pixfmt", "GRAY8")

            # Flip and rotation settings
            flip_left = camera_config.get("flip_left", False)
            flip_right = camera_config.get("flip_right", False)
            rotation_left = camera_config.get("rotation_left", 0.0)
            rotation_right = camera_config.get("rotation_right", 0.0)

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

                # Configure cameras with settings from config including flip and rotation correction
                self._left_camera.set_mode(width, height, fps, pixfmt, flip_180=flip_left, rotation_correction=rotation_left)
                self._right_camera.set_mode(width, height, fps, pixfmt, flip_180=flip_right, rotation_correction=rotation_right)

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

                # Configure cameras with settings from config including flip and rotation correction
                self._left_camera.set_mode(width, height, fps, pixfmt, flip_180=flip_left, rotation_correction=rotation_left)
                self._right_camera.set_mode(width, height, fps, pixfmt, flip_180=flip_right, rotation_correction=rotation_right)

            # Update status labels to show which camera is assigned to which position
            self._left_status.setText(f"● {self._left_serial}")
            self._left_status.setStyleSheet("color: green; font-weight: bold;")
            self._right_status.setText(f"● {self._right_serial}")
            self._right_status.setStyleSheet("color: green; font-weight: bold;")

            # NEW: Wait for cameras to warm up, then run alignment check
            QtCore.QTimer.singleShot(1000, self._wait_for_camera_warmup)

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
        """Update camera previews and check for ChArUco board."""
        if not self._left_camera or not self._right_camera:
            return

        try:
            # Get frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            if left_frame is None or right_frame is None:
                return

            # Check for ChArUco board in both cameras
            left_detected, left_image = self._detect_charuco(left_frame.image)
            right_detected, right_image = self._detect_charuco(right_frame.image)

            # Update previews
            self._update_view(self._left_view, left_image)
            self._update_view(self._right_view, right_image)

            # Update status indicators
            if left_detected:
                self._left_status.setText("● ChArUco board detected")
                self._left_status.setStyleSheet("color: green; font-weight: bold;")
            else:
                self._left_status.setText("● No ChArUco board")
                self._left_status.setStyleSheet("color: red; font-weight: bold;")

            if right_detected:
                self._right_status.setText("● ChArUco board detected")
                self._right_status.setStyleSheet("color: green; font-weight: bold;")
            else:
                self._right_status.setText("● No ChArUco board")
                self._right_status.setStyleSheet("color: red; font-weight: bold;")

            # Enable capture if both detected
            self._capture_button.setEnabled(left_detected and right_detected)

        except Exception:
            pass

    def _detect_charuco(self, image: np.ndarray) -> tuple[bool, np.ndarray]:
        """Detect ChArUco board and draw corners.

        Returns:
            (detected, annotated_image)
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

        # Get ArUco dictionary and detector parameters
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

        # Try newer API first (OpenCV 4.7+)
        try:
            detector_params = cv2.aruco.DetectorParameters()
            detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
            marker_corners, marker_ids, rejected = detector.detectMarkers(gray)
        except AttributeError:
            # Fall back to older API
            detector_params = cv2.aruco.DetectorParameters_create()
            marker_corners, marker_ids, rejected = cv2.aruco.detectMarkers(
                gray, aruco_dict, parameters=detector_params
            )

        # Check if any markers were detected
        if marker_ids is None or len(marker_ids) == 0:
            hint_text = f"Move {self._pattern_cols}x{self._pattern_rows} ChArUco board into shared view"
            cv2.putText(
                annotated,
                hint_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )
            return False, annotated

        # Draw detected markers
        cv2.aruco.drawDetectedMarkers(annotated, marker_corners, marker_ids)

        # Create ChArUco board
        try:
            # Try newer API first (OpenCV 4.7+)
            board = cv2.aruco.CharucoBoard(
                (self._pattern_cols, self._pattern_rows),
                self._square_size,
                self._square_size * 0.75,  # Marker size is 75% of square
                aruco_dict
            )
        except (AttributeError, TypeError):
            # Fall back to older API
            board = cv2.aruco.CharucoBoard_create(
                self._pattern_cols,
                self._pattern_rows,
                self._square_size,
                self._square_size * 0.75,
                aruco_dict
            )

        # Interpolate ChArUco corners
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
        if num_corners is not None and num_corners >= MIN_CORNERS:
            # Draw ChArUco corners
            cv2.aruco.drawDetectedCornersCharuco(annotated, charuco_corners, charuco_ids, (0, 255, 0))

            # Add corner count indicator
            cv2.putText(
                annotated,
                f"Corners: {num_corners}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            return True, annotated
        else:
            # Not enough corners detected
            corner_count = num_corners if num_corners is not None else 0
            cv2.putText(
                annotated,
                f"Need {MIN_CORNERS}+ corners (found {corner_count})",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),  # Orange
                2
            )
            return False, annotated

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

            # Store baseline alignment from first capture
            if len(self._captures) == 1:
                try:
                    from analysis.camera_alignment import analyze_alignment
                    self._baseline_alignment = analyze_alignment(left_frame.image, right_frame.image)
                except Exception:
                    pass  # Don't fail capture if alignment analysis fails

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Capture Error",
                f"Failed to capture image pair:\n{str(e)}",
            )

    def _check_alignment_drift(self, left_img: np.ndarray, right_img: np.ndarray) -> bool:
        """Check if camera alignment has drifted since first capture.

        Args:
            left_img: Current left camera image
            right_img: Current right camera image

        Returns:
            True if user chose to abort this capture (drift too large), False to continue
        """
        if self._baseline_alignment is None:
            return False  # No baseline, can't check drift

        try:
            from analysis.camera_alignment import analyze_alignment

            # Analyze current alignment
            current = analyze_alignment(left_img, right_img)

            # Calculate drift in key metrics
            toin_drift = abs(current.convergence_std_px - self._baseline_alignment.convergence_std_px)
            vertical_drift = abs(current.vertical_mean_px - self._baseline_alignment.vertical_mean_px)
            rotation_drift = abs(current.rotation_deg - self._baseline_alignment.rotation_deg)
            focal_drift = abs(current.scale_difference_percent - self._baseline_alignment.scale_difference_percent)

            # Determine if drift is significant
            # Thresholds: toe-in > 5px, vertical > 3px, rotation > 2°, focal > 3%
            significant_drift = (
                toin_drift > 5.0 or
                vertical_drift > 3.0 or
                rotation_drift > 2.0 or
                focal_drift > 3.0
            )

            if not significant_drift:
                return False  # No significant drift, continue

            # Build drift warning message
            drift_details = []
            if toin_drift > 5.0:
                drift_details.append(
                    f"  • Toe-in: {self._baseline_alignment.convergence_std_px:.1f}px → "
                    f"{current.convergence_std_px:.1f}px (Δ {toin_drift:.1f}px)"
                )
            if vertical_drift > 3.0:
                drift_details.append(
                    f"  • Vertical: {self._baseline_alignment.vertical_mean_px:.1f}px → "
                    f"{current.vertical_mean_px:.1f}px (Δ {vertical_drift:.1f}px)"
                )
            if rotation_drift > 2.0:
                drift_details.append(
                    f"  • Rotation: {self._baseline_alignment.rotation_deg:.1f}° → "
                    f"{current.rotation_deg:.1f}° (Δ {rotation_drift:.1f}°)"
                )
            if focal_drift > 3.0:
                drift_details.append(
                    f"  • Focal Length: {self._baseline_alignment.scale_difference_percent:.1f}% → "
                    f"{current.scale_difference_percent:.1f}% (Δ {focal_drift:.1f}%)"
                )

            warning_msg = (
                f"⚠️ Camera alignment has drifted since capture 1!\n\n"
                f"Changes detected:\n" + "\n".join(drift_details) + "\n\n"
                f"This can invalidate calibration. Recommendations:\n\n"
                f"• Click 'Restart' to clear captures and start over (recommended)\n"
                f"• Click 'Continue' to capture anyway (may reduce calibration quality)\n"
                f"• Click 'Cancel' to skip this capture and reposition cameras"
            )

            # Show warning dialog with options
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Alignment Drift Detected")
            msg_box.setText(warning_msg)

            restart_btn = msg_box.addButton("Restart Calibration", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
            continue_btn = msg_box.addButton("Continue Anyway", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            cancel_btn = msg_box.addButton("Cancel Capture", QtWidgets.QMessageBox.ButtonRole.RejectRole)

            msg_box.setDefaultButton(restart_btn)
            msg_box.exec()

            clicked = msg_box.clickedButton()

            if clicked == restart_btn:
                # Restart calibration - clear all captures
                self._captures.clear()
                self._baseline_alignment = None
                self._capture_count_label.setText(f"Captured: 0 / {self._min_captures} minimum")
                self._capture_count_label.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; color: #d32f2f; padding: 5px;"
                )
                self._calibrate_button.setEnabled(False)

                # Clear temp directory
                self._clear_temp_images()

                QtWidgets.QMessageBox.information(
                    self,
                    "Calibration Restarted",
                    "All captures cleared. Please start capturing again with stable camera positions."
                )
                return True  # Abort this capture

            elif clicked == cancel_btn:
                # Just skip this capture
                return True  # Abort this capture

            else:  # continue_btn
                # User chose to continue despite drift
                return False  # Allow capture to proceed

        except Exception as e:
            # Don't block captures if drift detection fails
            print(f"Warning: Alignment drift check failed: {e}")
            return False

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

        # Update baseline spinner with calibrated value
        calibrated_baseline = result['baseline_ft']
        self._baseline_spin.blockSignals(True)  # Don't trigger valueChanged
        self._baseline_spin.setValue(calibrated_baseline)
        self._baseline_spin.blockSignals(False)

        # Update baseline status to show it's now calibrated (blue)
        baseline_inches = calibrated_baseline * 12
        self._baseline_inches_label.setText(f"({baseline_inches:.1f} in) 📐 Calibrated")
        self._baseline_inches_label.setStyleSheet("color: #2196F3; font-style: italic; font-weight: bold;")
        self._baseline_inches_label.setToolTip(
            "This value was calculated by stereo calibration (more accurate than manual measurement)"
        )

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
            self._alignment_status_label.setStyleSheet(
                "font-size: 10pt; padding: 8px; "
                "background-color: #FFF9C4; "
                "border: 1px solid #FBC02D; "
                "border-radius: 4px;"
            )

            # Check both cameras
            left_stable, left_variance = check_camera_warmup(self._left_camera, num_frames=15)
            right_stable, right_variance = check_camera_warmup(self._right_camera, num_frames=15)

            both_stable = left_stable and right_stable

            if both_stable:
                # Cameras are stable - proceed with alignment check
                self._alignment_status_label.setText(
                    f"✓ Cameras stable (variance: L={left_variance:.3f}, R={right_variance:.3f})"
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
                    self._warmup_attempts = 0
                    QtCore.QTimer.singleShot(500, self._run_automatic_alignment_check)

        except Exception as e:
            # If warmup check fails, just proceed with alignment check
            print(f"Warning: Camera warmup check failed: {e}")
            self._warmup_attempts = 0
            QtCore.QTimer.singleShot(500, self._run_automatic_alignment_check)

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
            self._alignment_status_label.setStyleSheet(
                "font-size: 10pt; padding: 8px; "
                "color: #000000; "  # Dark text for readability
                "background-color: #E3F2FD; "
                "border: 1px solid #2196F3; "
                "border-radius: 4px;"
            )

            # Run alignment analysis with multi-frame averaging
            from analysis.camera_alignment import (
                analyze_alignment_averaged,
                apply_corrections,
                save_alignment_frames
            )

            results = analyze_alignment_averaged(
                self._left_camera,
                self._right_camera,
                num_frames=10,
                interval_ms=100
            )

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
                    print("INFO: Alignment corrections detected but NOT applied (auto-correct is disabled)")

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
            self._alignment_status_label.setStyleSheet(
                "font-size: 10pt; padding: 8px; "
                "background-color: #FFEBEE; "
                "border: 1px solid #F44336; "
                "border-radius: 4px; color: #C62828;"
            )
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
            self._alignment_status_label.setStyleSheet(
                "font-size: 10pt; padding: 8px; "
                "color: #000000; "  # Dark text for readability
                "background-color: #E3F2FD; "
                "border: 1px solid #2196F3; "
                "border-radius: 4px;"
            )

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
                    print("INFO: Alignment corrections detected but NOT applied (auto-correct is disabled)")

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
            self._alignment_status_label.setStyleSheet(
                "font-size: 10pt; padding: 8px; "
                "background-color: #FFEBEE; "
                "border: 1px solid #F44336; "
                "border-radius: 4px; color: #C62828;"
            )
            self._alignment_results = None

    def _display_alignment_results(self, results, quick_check: bool = False) -> None:
        """Display alignment results in the status widget.

        Args:
            results: AlignmentResults object from analysis
        """
        # Choose color and icon based on quality
        if results.quality == "CRITICAL":
            bg_color = "#FFEBEE"
            border_color = "#F44336"
            text_color = "#C62828"
            icon = "❌"
        elif results.quality == "POOR":
            bg_color = "#FFF3E0"
            border_color = "#FF9800"
            text_color = "#E65100"
            icon = "⚠️"
        elif results.quality == "ACCEPTABLE":
            bg_color = "#FFF9C4"
            border_color = "#FBC02D"
            text_color = "#F57F17"
            icon = "🟡"
        elif results.quality == "GOOD":
            bg_color = "#E8F5E9"
            border_color = "#4CAF50"
            text_color = "#2E7D32"
            icon = "✓"
        else:  # EXCELLENT
            bg_color = "#E8F5E9"
            border_color = "#4CAF50"
            text_color = "#1B5E20"
            icon = "✅"

        # Build status message
        status_html = f"<b>{icon} {results.status_message}</b>"

        # Add badge if quick check
        if quick_check:
            status_html += " <span style='background-color: #FFC107; color: black; padding: 2px 6px; border-radius: 3px; font-size: 8pt;'>⚡ QUICK CHECK</span>"
            status_html += "<br><i style='font-size: 9pt;'>Single-frame analysis - run Full Check for averaged results</i>"

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
        self._alignment_status_label.setStyleSheet(
            f"font-size: 10pt; padding: 8px; "
            f"background-color: {bg_color}; "
            f"border: 2px solid {border_color}; "
            f"border-radius: 4px; "
            f"color: {text_color};"
        )

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
        issues_count = sum([
            results.scale_difference_percent > 2.0,
            results.convergence_std_px > 5.0,
            abs(results.vertical_mean_px) > 5.0,
            abs(results.rotation_deg) > 1.0 and not results.rotation_correction_needed
        ])

        # Choose gauge color based on score
        if quality_score >= 90:
            gauge_color = "#4CAF50"  # Green
            gauge_emoji = "✅"
        elif quality_score >= 75:
            gauge_color = "#8BC34A"  # Light green
            gauge_emoji = "✓"
        elif quality_score >= 60:
            gauge_color = "#FFC107"  # Yellow
            gauge_emoji = "🟡"
        elif quality_score >= 40:
            gauge_color = "#FF9800"  # Orange
            gauge_emoji = "⚠️"
        else:
            gauge_color = "#F44336"  # Red
            gauge_emoji = "❌"

        gauge_html = f"""
        <div style='text-align: center;'>
            <div style='font-size: 32pt; color: {gauge_color};'>{gauge_emoji}</div>
            <div style='font-size: 20pt; color: {gauge_color}; font-weight: bold;'>{quality_score}%</div>
            <div style='font-size: 9pt; color: #666;'>{results.quality}</div>
            <div style='font-size: 9pt; color: #888;'>
                {issues_count} issue{'s' if issues_count != 1 else ''} detected
            </div>
        </div>
        """
        self._quality_gauge.setText(gauge_html)
        self._quality_gauge.setStyleSheet(
            f"font-size: 11pt; font-weight: bold; padding: 12px; "
            f"background-color: {gauge_color}20; "  # 20 = 12% opacity
            f"border: 2px solid {gauge_color}; "
            f"border-radius: 8px;"
        )
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

    def _update_alignment_history(self, results) -> None:
        """Add current results to history and update display.

        Args:
            results: AlignmentResults object to add to history
        """
        from datetime import datetime

        # Add to history list
        self._alignment_history.append({
            'timestamp': datetime.now(),
            'quality': results.quality,
            'focal': results.scale_difference_percent,
            'toin': results.convergence_std_px,
            'vertical': results.vertical_mean_px,
            'rotation': results.rotation_deg
        })

        # Update history display
        history_text = ""
        for i, entry in enumerate(self._alignment_history, 1):
            history_text += f"Iteration {i} ({entry['timestamp'].strftime('%H:%M:%S')}):\n"
            history_text += f"  Focal: {entry['focal']:5.1f}% | "
            history_text += f"Toe-in: {entry['toin']:5.1f}px | "
            history_text += f"Vertical: {entry['vertical']:5.1f}px | "
            history_text += f"Quality: {entry['quality']}\n\n"

        self._history_list.setText(history_text)
        self._history_group.show()

        # NEW: Auto-save history to file
        self._save_alignment_history()

    def _save_alignment_history(self) -> None:
        """Save alignment history to JSON file for persistence across sessions."""
        try:
            import json
            from datetime import datetime

            history_file = Path("alignment_checks/history.json")
            history_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing history file (if exists)
            if history_file.exists():
                try:
                    existing_data = json.loads(history_file.read_text())
                except:
                    existing_data = {"sessions": []}
            else:
                existing_data = {"sessions": []}

            # Create current session entry
            session_entry = {
                "session_date": datetime.now().isoformat(),
                "camera_serials": {
                    "left": self._left_serial,
                    "right": self._right_serial
                },
                "iterations": []
            }

            # Convert history entries to serializable format
            for entry in self._alignment_history:
                session_entry["iterations"].append({
                    "timestamp": entry["timestamp"].isoformat(),
                    "quality": entry["quality"],
                    "focal_diff_percent": entry["focal"],
                    "toin_std_px": entry["toin"],
                    "vertical_mean_px": entry["vertical"],
                    "rotation_deg": entry["rotation"]
                })

            # Append to sessions
            existing_data["sessions"].append(session_entry)

            # Keep only last 10 sessions to prevent file from growing too large
            if len(existing_data["sessions"]) > 10:
                existing_data["sessions"] = existing_data["sessions"][-10:]

            # Write back to file
            history_file.write_text(json.dumps(existing_data, indent=2))

        except Exception as e:
            # Don't fail alignment check if saving history fails
            print(f"Warning: Could not save alignment history: {e}")

    def _load_alignment_history(self) -> None:
        """Load previous alignment history from file (for current session display)."""
        try:
            import json

            history_file = Path("alignment_checks/history.json")
            if not history_file.exists():
                return

            data = json.loads(history_file.read_text())

            # Show summary of past sessions in history widget if no current history
            if len(self._alignment_history) == 0 and len(data.get("sessions", [])) > 0:
                past_sessions_text = "<b>Previous Sessions:</b>\n\n"

                for session in data["sessions"][-5:]:  # Show last 5 sessions
                    date = session["session_date"][:10]  # Just date part
                    iterations = session["iterations"]

                    if len(iterations) > 0:
                        first = iterations[0]
                        last = iterations[-1]

                        past_sessions_text += f"📅 {date} ({len(iterations)} checks):\n"
                        past_sessions_text += f"  Started: {first['quality']} "
                        past_sessions_text += f"(Focal: {first['focal_diff_percent']:.1f}%, "
                        past_sessions_text += f"Toe-in: {first['toin_std_px']:.1f}px)\n"

                        if len(iterations) > 1:
                            past_sessions_text += f"  Ended:   {last['quality']} "
                            past_sessions_text += f"(Focal: {last['focal_diff_percent']:.1f}%, "
                            past_sessions_text += f"Toe-in: {last['toin_std_px']:.1f}px)\n"

                        past_sessions_text += "\n"

                self._history_list.setText(past_sessions_text)
                self._history_group.show()

        except Exception as e:
            print(f"Warning: Could not load alignment history: {e}")

    def _show_feature_overlay(self) -> None:
        """Show visual overlay of matched features on camera previews."""
        if not self._left_camera or not self._right_camera:
            QtWidgets.QMessageBox.warning(
                self,
                "Cameras Not Ready",
                "Cameras must be active to visualize features."
            )
            return

        try:
            # Capture current frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            # Create visualization
            from analysis.camera_alignment import visualize_features, _find_feature_matches
            pts1, pts2 = _find_feature_matches(left_frame.image, right_frame.image, max_features=1000)
            vis_img = visualize_features(left_frame.image, right_frame.image, pts1, pts2)

            # Convert to QPixmap for display
            height, width, channels = vis_img.shape
            bytes_per_line = channels * width
            q_image = QtGui.QImage(
                vis_img.data,
                width,
                height,
                bytes_per_line,
                QtGui.QImage.Format.Format_RGB888,
            )
            pixmap = QtGui.QPixmap.fromImage(q_image)

            # Create dialog to display
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Feature Matches Visualization")
            dialog.resize(1200, 500)

            layout = QtWidgets.QVBoxLayout()

            # Info label
            info_label = QtWidgets.QLabel(
                f"<b>{len(pts1)} matched features</b><br>"
                f"Green circles show corresponding points between cameras.<br>"
                f"Good feature distribution indicates proper alignment."
            )
            info_label.setWordWrap(True)
            layout.addWidget(info_label)

            # Image display
            image_label = QtWidgets.QLabel()
            scaled_pixmap = pixmap.scaled(
                1180, 440,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            image_label.setPixmap(scaled_pixmap)
            layout.addWidget(image_label)

            # Close button
            close_btn = QtWidgets.QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.setLayout(layout)
            dialog.exec()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Feature Visualization Error",
                f"Failed to visualize features:\n{str(e)}"
            )

    def _show_alignment_details(self) -> None:
        """Show detailed alignment report dialog."""
        if not hasattr(self, '_alignment_results') or self._alignment_results is None:
            return

        results = self._alignment_results

        # Build detailed report
        report = (
            f"<h3>Camera Alignment Detailed Report</h3>"
            f"<p><b>Overall Quality:</b> {results.quality}</p>"
            f"<hr>"
            f"<h4>Vertical Alignment (Height)</h4>"
            f"<p><b>Status:</b> {results.vertical_status}<br>"
            f"<b>Mean offset:</b> {results.vertical_mean_px:.2f} px<br>"
            f"<b>Max offset:</b> {results.vertical_max_px:.2f} px</p>"
            f"<hr>"
            f"<h4>Horizontal Alignment (Toe-in/Convergence)</h4>"
            f"<p><b>Status:</b> {results.horizontal_status}<br>"
            f"<b>Disparity std dev:</b> {results.convergence_std_px:.2f} px<br>"
            f"<b>Position correlation:</b> {results.correlation:.3f}<br>"
            f"<i>(Should be >0.9 for parallel cameras)</i></p>"
            f"<hr>"
            f"<h4>Rotation Alignment (Roll)</h4>"
            f"<p><b>Status:</b> {results.rotation_status}<br>"
            f"<b>Rotation difference:</b> {results.rotation_deg:.2f}°</p>"
            f"<hr>"
            f"<h4>Focal Length / Scale</h4>"
            f"<p><b>Status:</b> {results.scale_status}<br>"
            f"<b>Scale difference:</b> {results.scale_difference_percent:.2f}%<br>"
            f"<i>(Indicates if one camera is more zoomed in than the other)</i></p>"
            f"<hr>"
            f"<h4>Feature Matches</h4>"
            f"<p><b>Matches found:</b> {results.num_matches}</p>"
        )

        if results.corrections_applied:
            report += "<hr><h4>Software Corrections Applied</h4><ul>"
            for correction in results.corrections_applied:
                report += f"<li>{correction}</li>"
            report += "</ul>"

        if results.warnings:
            report += "<hr><h4>Recommendations</h4><ul>"
            for warning in results.warnings:
                report += f"<li>{warning}</li>"
            report += "</ul>"

        # Show in dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Camera Alignment Details")
        dialog.resize(600, 500)

        layout = QtWidgets.QVBoxLayout()

        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setHtml(report)
        layout.addWidget(text)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def _export_alignment_report(self) -> None:
        """Export alignment report as HTML file."""
        if not hasattr(self, '_alignment_results') or self._alignment_results is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No Report Available",
                "Run an alignment check first before exporting a report."
            )
            return

        try:
            from datetime import datetime
            from analysis.camera_alignment import generate_html_report

            # Generate HTML report
            html = generate_html_report(
                self._alignment_results,
                self._left_serial or "Unknown",
                self._right_serial or "Unknown"
            )

            # Prompt user for save location
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"alignment_report_{timestamp}.html"

            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export Alignment Report",
                str(Path("alignment_checks") / default_filename),
                "HTML Files (*.html);;All Files (*.*)"
            )

            if filename:
                # Save HTML file
                Path(filename).parent.mkdir(parents=True, exist_ok=True)
                Path(filename).write_text(html, encoding='utf-8')

                # Ask if user wants to open the report
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Report Exported",
                    f"Alignment report exported successfully to:\n{filename}\n\n"
                    f"Would you like to open it now?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes
                )

                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    # Open in default browser
                    import webbrowser
                    webbrowser.open(f"file:///{Path(filename).absolute()}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export alignment report:\n{str(e)}"
            )

    def _save_alignment_preset(self) -> None:
        """Save current alignment as a preset."""
        if not hasattr(self, '_alignment_results') or self._alignment_results is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No Alignment Available",
                "Run an alignment check first before saving a preset."
            )
            return

        try:
            from datetime import datetime
            from analysis.camera_alignment import save_alignment_preset

            # Prompt for preset name
            default_name = f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            preset_name, ok = QtWidgets.QInputDialog.getText(
                self,
                "Save Alignment Preset",
                "Enter a name for this preset:\n(e.g., 'baseline_good', 'after_adjustment')",
                QtWidgets.QLineEdit.EchoMode.Normal,
                default_name
            )

            if ok and preset_name:
                # Save preset
                save_alignment_preset(
                    self._alignment_results,
                    preset_name,
                    self._left_serial or "Unknown",
                    self._right_serial or "Unknown"
                )

                QtWidgets.QMessageBox.information(
                    self,
                    "Preset Saved",
                    f"Alignment preset '{preset_name}' saved successfully!\n\n"
                    f"Quality Score: {self._alignment_results.get_quality_score()}%\n"
                    f"You can load this preset later for comparison."
                )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save alignment preset:\n{str(e)}"
            )

    def _load_alignment_preset(self) -> None:
        """Load a saved alignment preset and display it."""
        try:
            from analysis.camera_alignment import list_alignment_presets, load_alignment_preset

            # Get list of available presets
            presets = list_alignment_presets()

            if not presets:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Presets Found",
                    "No saved alignment presets found.\n\n"
                    "Save a preset first by running an alignment check "
                    "and clicking 'Save Preset'."
                )
                return

            # Show selection dialog
            preset_names = [f"{p['name']} ({p['quality_score']}% - {p['saved_at'][:10]})"
                           for p in presets]

            preset_choice, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Load Alignment Preset",
                "Select a preset to view:",
                preset_names,
                0,
                False
            )

            if ok and preset_choice:
                # Extract preset name (before the parenthesis)
                preset_name = preset_choice.split(" (")[0]

                # Load preset data
                preset_data = load_alignment_preset(preset_name)
                if not preset_data:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Load Failed",
                        f"Could not load preset '{preset_name}'"
                    )
                    return

                # Display preset details
                metrics = preset_data["metrics"]
                info_text = (
                    f"<h3>Preset: {preset_data['preset_name']}</h3>"
                    f"<p><b>Saved:</b> {preset_data['saved_at'][:19]}<br>"
                    f"<b>Cameras:</b> {preset_data['left_camera']} / {preset_data['right_camera']}<br>"
                    f"<b>Quality Score:</b> {preset_data['quality_score']}% ({preset_data['quality_rating']})</p>"
                    f"<hr>"
                    f"<h4>Metrics:</h4>"
                    f"<table>"
                    f"<tr><td><b>Focal Length Diff:</b></td><td>{metrics['focal_diff_percent']:.2f}%</td></tr>"
                    f"<tr><td><b>Toe-in:</b></td><td>{metrics['toin_std_px']:.2f} px</td></tr>"
                    f"<tr><td><b>Vertical Offset:</b></td><td>{metrics['vertical_mean_px']:.2f} px</td></tr>"
                    f"<tr><td><b>Rotation:</b></td><td>{metrics['rotation_deg']:.2f}°</td></tr>"
                    f"<tr><td><b>Feature Matches:</b></td><td>{metrics['num_matches']}</td></tr>"
                    f"</table>"
                )

                # Show in dialog
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle("Alignment Preset Details")
                dialog.resize(500, 400)

                layout = QtWidgets.QVBoxLayout()

                text = QtWidgets.QTextEdit()
                text.setReadOnly(True)
                text.setHtml(info_text)
                layout.addWidget(text)

                close_btn = QtWidgets.QPushButton("Close")
                close_btn.clicked.connect(dialog.accept)
                layout.addWidget(close_btn)

                dialog.setLayout(layout)
                dialog.exec()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Load Failed",
                f"Failed to load preset:\n{str(e)}"
            )

    def _compare_with_preset(self) -> None:
        """Compare current alignment with a saved preset (side-by-side)."""
        if not hasattr(self, '_alignment_results') or self._alignment_results is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No Current Alignment",
                "Run an alignment check first before comparing."
            )
            return

        try:
            from analysis.camera_alignment import (
                list_alignment_presets,
                load_alignment_preset,
                compare_with_preset
            )

            # Get list of available presets
            presets = list_alignment_presets()

            if not presets:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Presets Found",
                    "No saved alignment presets found.\n\n"
                    "Save a preset first to enable comparison."
                )
                return

            # Show selection dialog
            preset_names = [f"{p['name']} ({p['quality_score']}% - {p['saved_at'][:10]})"
                           for p in presets]

            preset_choice, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Compare with Preset",
                "Select a preset to compare with current alignment:",
                preset_names,
                0,
                False
            )

            if ok and preset_choice:
                # Extract preset name
                preset_name = preset_choice.split(" (")[0]

                # Load preset
                preset_data = load_alignment_preset(preset_name)
                if not preset_data:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Load Failed",
                        f"Could not load preset '{preset_name}'"
                    )
                    return

                # Perform comparison
                comparison = compare_with_preset(self._alignment_results, preset_data)

                # Build comparison display
                trend_color = "#4CAF50" if comparison["trend"] == "BETTER" else (
                    "#F44336" if comparison["trend"] == "WORSE" else "#FFC107"
                )

                comparison_html = f"""
                <h3>Alignment Comparison</h3>
                <p><b>Current vs. Preset:</b> {comparison['preset_name']} ({comparison['preset_date']})</p>
                <div style='text-align: center; padding: 15px; background-color: {trend_color}20;
                            border: 2px solid {trend_color}; border-radius: 8px; margin: 10px 0;'>
                    <div style='font-size: 32pt;'>{comparison['trend_emoji']}</div>
                    <div style='font-size: 16pt; font-weight: bold; color: {trend_color};'>
                        {comparison['trend']}
                    </div>
                    <div style='font-size: 12pt; margin-top: 5px;'>
                        Score: {comparison['current_score']}% vs {comparison['preset_score']}%
                        ({comparison['score_delta']:+.0f})
                    </div>
                </div>
                <hr>
                <h4>Detailed Comparison:</h4>
                <table style='width: 100%;'>
                    <tr style='background-color: #f5f5f5;'>
                        <th>Metric</th>
                        <th>Current</th>
                        <th>Preset</th>
                        <th>Δ</th>
                        <th>Status</th>
                    </tr>
                """

                for metric_name, metric_label in [
                    ("focal", "Focal Length"),
                    ("toin", "Toe-in"),
                    ("vertical", "Vertical"),
                    ("rotation", "Rotation")
                ]:
                    delta_data = comparison["deltas"][metric_name]
                    status_emoji = "✓" if delta_data["better"] else "⚠️"
                    status_color = "#4CAF50" if delta_data["better"] else "#FF9800"

                    comparison_html += f"""
                    <tr>
                        <td><b>{metric_label}</b></td>
                        <td>{delta_data['current']:.2f}</td>
                        <td>{delta_data['preset']:.2f}</td>
                        <td>{delta_data['delta']:+.2f}</td>
                        <td style='color: {status_color}; font-weight: bold;'>{status_emoji}</td>
                    </tr>
                    """

                comparison_html += "</table>"

                # Show in dialog
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle("Alignment Comparison")
                dialog.resize(650, 500)

                layout = QtWidgets.QVBoxLayout()

                text = QtWidgets.QTextEdit()
                text.setReadOnly(True)
                text.setHtml(comparison_html)
                layout.addWidget(text)

                close_btn = QtWidgets.QPushButton("Close")
                close_btn.clicked.connect(dialog.accept)
                layout.addWidget(close_btn)

                dialog.setLayout(layout)
                dialog.exec()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Comparison Failed",
                f"Failed to compare with preset:\n{str(e)}"
            )

    def _restart_cameras_after_correction(self) -> None:
        """Restart cameras after applying alignment corrections."""
        try:
            # Stop preview
            self._preview_timer.stop()

            # Close cameras
            self._close_cameras()

            # Wait briefly
            QtCore.QTimer.singleShot(500, self._reopen_cameras_after_correction)

        except Exception as e:
            print(f"Error restarting cameras: {e}")

    def _reopen_cameras_after_correction(self) -> None:
        """Reopen cameras after applying corrections."""
        try:
            # Reopen with corrections applied
            self._open_cameras()

            # Restart preview
            self._preview_timer.start(33)  # 30 FPS

            # Update UI
            self._alignment_status_label.setText(
                self._alignment_status_label.text().replace(
                    "Rotation correction applied",
                    "Rotation correction applied ✓ (cameras restarted)"
                )
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Camera Error",
                f"Failed to restart cameras after applying corrections:\n{str(e)}"
            )
