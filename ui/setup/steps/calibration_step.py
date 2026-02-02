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

        # Calibration settings (default pattern)
        self._pattern_cols = 5  # Default: 5 columns
        self._pattern_rows = 6  # Default: 6 rows
        self._square_mm = 30.0  # Default: 30mm square size
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

        # Detection optimization (prevent processing loop)
        self._cached_dict_name: Optional[str] = None  # Best dictionary found
        self._dict_scan_counter: int = 0  # Only rescan every N frames
        self._last_auto_detect_time: float = 0  # Debounce auto-detection
        self._detection_log_counter: int = 0  # Reduce log spam
        self._pattern_locked: bool = False  # Lock pattern once auto-detected
        self._user_changed_pattern: bool = False  # Track if user manually changed pattern

        # Smart calibration features
        self._show_marker_overlay: bool = True  # Show marker position indicators
        self._camera_history_file: Path = Path("configs") / "camera_history.json"  # Track camera assignments
        self._detected_patterns: list = []  # Multiple detected ChArUco patterns
        self._auto_swap_on_startup: bool = True  # Auto-check camera orientation on startup

        self._build_ui()

        # Preview timer
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)

    def _build_ui(self) -> None:
        """Build simplified calibration step UI."""
        layout = QtWidgets.QVBoxLayout()

        # Simple instruction at top
        instruction = QtWidgets.QLabel(
            "<b style='font-size: 14pt;'>📷 Capture 10+ ChArUco Board Poses</b>"
        )
        instruction.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        instruction.setStyleSheet("padding: 10px; background-color: #E3F2FD; border-radius: 5px; color: #000000;")
        layout.addWidget(instruction)

        # Progress bar showing captures
        progress_layout = QtWidgets.QHBoxLayout()
        self._capture_count_label = QtWidgets.QLabel("Progress: 0/10 poses captured")
        self._capture_count_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #000000;")

        self._capture_progress_bar = QtWidgets.QProgressBar()
        self._capture_progress_bar.setMinimum(0)
        self._capture_progress_bar.setMaximum(10)
        self._capture_progress_bar.setValue(0)
        self._capture_progress_bar.setFormat("%v/%m")
        self._capture_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4CAF50;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
                font-size: 11pt;
                min-height: 30px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)

        progress_layout.addWidget(self._capture_count_label, 1)
        progress_layout.addWidget(self._capture_progress_bar, 3)
        layout.addLayout(progress_layout)

        # Camera previews (LARGE - 80% of screen)
        preview_layout = QtWidgets.QHBoxLayout()

        # Left preview
        left_group = QtWidgets.QGroupBox()
        left_group.setTitle("")  # No title for cleaner look
        self._left_view = QtWidgets.QLabel("No preview")
        self._left_view.setMinimumSize(800, 600)  # Much larger preview
        self._left_view.setScaledContents(True)
        self._left_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_view.setStyleSheet("background-color: #2c3e50; color: white; border: 2px solid #34495e;")

        # Simple status - just READY or NOT READY
        self._left_status = QtWidgets.QLabel("⏳ Waiting for board...")
        self._left_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_status.setStyleSheet(
            "font-size: 14pt; font-weight: bold; padding: 8px; "
            "background-color: #95a5a6; color: #000000; border-radius: 5px;"
        )

        # Focus quality indicator
        self._left_focus = QtWidgets.QLabel("Focus: Unknown")
        self._left_focus.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_focus.setStyleSheet(
            "font-size: 12pt; font-weight: bold; padding: 6px; "
            "background-color: #34495e; color: #FFFFFF; border-radius: 3px;"
        )

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(QtWidgets.QLabel("<b>LEFT CAMERA</b>"), alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self._left_view, 10)  # 10x stretch for large preview
        left_layout.addWidget(self._left_status)
        left_layout.addWidget(self._left_focus)
        left_group.setLayout(left_layout)

        # Right preview
        right_group = QtWidgets.QGroupBox()
        right_group.setTitle("")  # No title for cleaner look
        self._right_view = QtWidgets.QLabel("No preview")
        self._right_view.setMinimumSize(800, 600)  # Much larger preview
        self._right_view.setScaledContents(True)
        self._right_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_view.setStyleSheet("background-color: #2c3e50; color: white; border: 2px solid #34495e;")

        # Simple status - just READY or NOT READY
        self._right_status = QtWidgets.QLabel("⏳ Waiting for board...")
        self._right_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_status.setStyleSheet(
            "font-size: 14pt; font-weight: bold; padding: 8px; "
            "background-color: #95a5a6; color: #000000; border-radius: 5px;"
        )

        # Focus quality indicator
        self._right_focus = QtWidgets.QLabel("Focus: Unknown")
        self._right_focus.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_focus.setStyleSheet(
            "font-size: 12pt; font-weight: bold; padding: 6px; "
            "background-color: #34495e; color: #FFFFFF; border-radius: 3px;"
        )

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(QtWidgets.QLabel("<b>RIGHT CAMERA</b>"), alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self._right_view, 10)  # 10x stretch for large preview
        right_layout.addWidget(self._right_status)
        right_layout.addWidget(self._right_focus)
        right_group.setLayout(right_layout)

        preview_layout.addWidget(left_group)
        preview_layout.addWidget(right_group)
        layout.addLayout(preview_layout, 10)  # Give previews most of the space

        # Controls - Large buttons for capture and calibration
        controls_layout = QtWidgets.QHBoxLayout()

        self._capture_button = QtWidgets.QPushButton("📷 Capture Pose")
        self._capture_button.setMinimumHeight(50)
        self._capture_button.setMinimumWidth(200)
        self._capture_button.setEnabled(False)
        self._capture_button.setStyleSheet("""
            QPushButton {
                font-size: 14pt;
                font-weight: bold;
                background-color: #95a5a6;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:enabled {
                background-color: #4CAF50;
            }
            QPushButton:enabled:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self._capture_button.clicked.connect(self._capture_image_pair)

        self._calibrate_button = QtWidgets.QPushButton("🔧 Run Calibration")
        self._calibrate_button.setMinimumHeight(50)
        self._calibrate_button.setMinimumWidth(200)
        self._calibrate_button.setEnabled(False)
        self._calibrate_button.setStyleSheet("""
            QPushButton {
                font-size: 14pt;
                font-weight: bold;
                background-color: #95a5a6;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:enabled {
                background-color: #2196F3;
            }
            QPushButton:enabled:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        self._calibrate_button.clicked.connect(self._run_calibration)

        controls_layout.addStretch()
        controls_layout.addWidget(self._capture_button)
        controls_layout.addWidget(self._calibrate_button)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Advanced Settings - Collapsible section (collapsed by default)
        advanced_group = QtWidgets.QGroupBox("⚙️ Advanced Settings")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)  # Collapsed by default
        advanced_group.setStyleSheet("""
            QGroupBox {
                font-size: 11pt;
                font-weight: bold;
                border: 2px solid #9E9E9E;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        advanced_layout = QtWidgets.QVBoxLayout()

        # Add settings group (pattern, camera flips, baseline, etc.)
        settings_widget = self._build_settings_group()
        advanced_layout.addWidget(settings_widget)

        # Add alignment widget
        alignment_widget = self._build_alignment_widget()
        advanced_layout.addWidget(alignment_widget)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Release cameras button (for emergencies) - Small and tucked away
        self._release_button = QtWidgets.QPushButton("🔓 Force Release Cameras")
        self._release_button.setMaximumWidth(200)
        self._release_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                font-weight: bold;
                font-size: 9pt;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        self._release_button.clicked.connect(self._force_release_cameras)
        release_layout = QtWidgets.QHBoxLayout()
        release_layout.addStretch()
        release_layout.addWidget(self._release_button)
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
        self._square_spin.valueChanged.connect(self._on_square_size_changed)

        # Auto-detection toggle
        self._auto_detect_pattern_checkbox = QtWidgets.QCheckBox("Enable Auto-Detection")
        self._auto_detect_pattern_checkbox.setChecked(True)  # ON by default
        self._auto_detect_pattern_checkbox.setToolTip(
            "When enabled, automatically detects ChArUco board size and dictionary.\n"
            "When disabled, uses the manual pattern settings above.\n\n"
            "Disable this if you want to force a specific board size\n"
            "or if auto-detection is causing issues."
        )
        self._auto_detect_pattern_checkbox.setStyleSheet("font-weight: bold; color: #2196F3;")
        self._auto_detect_pattern_checkbox.stateChanged.connect(self._on_auto_detect_toggled)

        # Pattern detection info label
        self._pattern_info_label = QtWidgets.QLabel("No pattern detected")
        self._pattern_info_label.setStyleSheet("font-size: 9pt; color: #666;")
        self._pattern_info_label.setToolTip("Shows currently detected ChArUco pattern and dictionary")

        board_layout.addWidget(pattern_label)
        board_layout.addWidget(self._pattern_cols_spin)
        board_layout.addWidget(cross_label)
        board_layout.addWidget(self._pattern_rows_spin)
        board_layout.addWidget(QtWidgets.QLabel("  |  "))
        board_layout.addWidget(square_label)
        board_layout.addWidget(self._square_spin)
        board_layout.addWidget(QtWidgets.QLabel("  |  "))
        board_layout.addWidget(self._auto_detect_pattern_checkbox)
        board_layout.addWidget(QtWidgets.QLabel("  |  "))
        board_layout.addWidget(self._pattern_info_label)
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

        # Manual rotation controls
        rotate_left_label = QtWidgets.QLabel("Rotate L:")
        self._rotate_left_spin = QtWidgets.QDoubleSpinBox()
        self._rotate_left_spin.setRange(-45.0, 45.0)
        self._rotate_left_spin.setSingleStep(0.5)
        self._rotate_left_spin.setDecimals(1)
        self._rotate_left_spin.setSuffix("°")
        self._rotate_left_spin.setToolTip("Manually rotate left camera (positive = clockwise, negative = counter-clockwise)")

        rotate_right_label = QtWidgets.QLabel("Rotate R:")
        self._rotate_right_spin = QtWidgets.QDoubleSpinBox()
        self._rotate_right_spin.setRange(-45.0, 45.0)
        self._rotate_right_spin.setSingleStep(0.5)
        self._rotate_right_spin.setDecimals(1)
        self._rotate_right_spin.setSuffix("°")
        self._rotate_right_spin.setToolTip("Manually rotate right camera (positive = clockwise, negative = counter-clockwise)")

        # Load current rotation values from config
        try:
            rotation_left = config_data.get("camera", {}).get("rotation_left", 0.0)
            rotation_right = config_data.get("camera", {}).get("rotation_right", 0.0)
            self._rotate_left_spin.setValue(rotation_left)
            self._rotate_right_spin.setValue(rotation_right)
        except Exception:
            self._rotate_left_spin.setValue(0.0)
            self._rotate_right_spin.setValue(0.0)

        # Connect after setting initial values to avoid triggering restart
        self._rotate_left_spin.valueChanged.connect(lambda val: self._set_manual_rotation("left", val))
        self._rotate_right_spin.valueChanged.connect(lambda val: self._set_manual_rotation("right", val))

        # Reset corrections button
        self._reset_corrections_btn = QtWidgets.QPushButton("🔄 Reset All")
        self._reset_corrections_btn.setToolTip("Reset all rotation and offset corrections to zero")
        self._reset_corrections_btn.clicked.connect(self._reset_all_corrections)
        self._reset_corrections_btn.setStyleSheet("background-color: #607D8B; color: white; font-weight: bold;")

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

        # Swap L/R button (manual)
        self._swap_lr_btn = QtWidgets.QPushButton("🔄 Swap L/R")
        self._swap_lr_btn.setToolTip("Manually swap left and right camera assignments")
        self._swap_lr_btn.clicked.connect(self._swap_left_right)
        self._swap_lr_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 5px 10px; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )

        # Auto-swap button (intelligent swap based on marker positions)
        self._auto_swap_btn = QtWidgets.QPushButton("🔍 Auto-Swap")
        self._auto_swap_btn.setToolTip(
            "Intelligently detect which camera should be left/right\n"
            "based on ChArUco marker positions.\n\n"
            "Hold board in view of both cameras and click this button.\n"
            "System will analyze marker positions and swap if needed."
        )
        self._auto_swap_btn.clicked.connect(self._auto_swap_cameras)
        self._auto_swap_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 5px 10px; }"
            "QPushButton:hover { background-color: #45a049; }"
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
        baseline_ft = 1.625  # Initialize with default
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
        camera_layout.addWidget(QtWidgets.QLabel("  |  "))
        camera_layout.addWidget(rotate_left_label)
        camera_layout.addWidget(self._rotate_left_spin)
        camera_layout.addWidget(rotate_right_label)
        camera_layout.addWidget(self._rotate_right_spin)
        camera_layout.addWidget(self._reset_corrections_btn)
        camera_layout.addWidget(QtWidgets.QLabel("  |  "))
        camera_layout.addWidget(self._swap_lr_btn)
        camera_layout.addWidget(self._auto_swap_btn)
        camera_layout.addWidget(QtWidgets.QLabel("  |  "))
        camera_layout.addWidget(self._auto_correct_checkbox)
        camera_layout.addStretch()
        camera_group.setLayout(camera_layout)

        # Baseline row (separate row to avoid cramping)
        baseline_layout = QtWidgets.QHBoxLayout()
        baseline_layout.addWidget(baseline_label)
        baseline_layout.addWidget(self._baseline_spin)
        baseline_layout.addWidget(self._baseline_inches_label)
        baseline_layout.addStretch()

        baseline_group = QtWidgets.QGroupBox("Stereo Baseline")
        baseline_group.setLayout(baseline_layout)

        main_layout.addWidget(board_group)
        main_layout.addWidget(camera_group)
        main_layout.addWidget(baseline_group)
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
        status_scroll.setMinimumHeight(100)  # Minimum height to show content
        status_scroll.setMaximumHeight(200)  # Increased from 150px to show more issues
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
            "font-size: 10pt; padding: 6px; "
            "color: #000000; "  # Black text for readability
            "background-color: #F5F5F5; "
            "border: 1px solid #E0E0E0; "
            "border-radius: 4px;"
        )
        self._alignment_details.hide()
        layout.addWidget(self._alignment_details)

        # NEW: Directional Guidance (hidden by default)
        self._guidance_label = QtWidgets.QLabel()
        self._guidance_label.setWordWrap(True)
        self._guidance_label.setStyleSheet(
            "font-size: 10pt; padding: 8px; "
            "color: #000000; "  # Black text for readability
            "background-color: #FFF9C4; "
            "border: 2px solid #FBC02D; "
            "border-radius: 4px;"
        )
        self._guidance_label.hide()
        layout.addWidget(self._guidance_label)

        # NEW: Predicted Calibration Quality (hidden by default)
        self._prediction_label = QtWidgets.QLabel()
        self._prediction_label.setWordWrap(True)
        self._prediction_label.setStyleSheet(
            "font-size: 10pt; padding: 8px; "
            "color: #000000; "  # Black text for readability
            "background-color: #E8F5E9; "
            "border: 2px solid #4CAF50; "
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
        print(f"[CalibrationStep] on_enter() called")
        print(f"  Current left serial: '{self._left_serial}'")
        print(f"  Current right serial: '{self._right_serial}'")

        # Clear any old calibration images from temp directory
        self._clear_temp_images()

        # Reset capture state
        self._captures.clear()
        self._baseline_alignment = None  # Reset drift detection baseline
        self._warmup_attempts = 0  # Reset warmup counter
        self._capture_count_label.setText(f"Progress: 0/{self._min_captures} poses captured")
        self._capture_count_label.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: #d32f2f;"
        )
        self._capture_progress_bar.setValue(0)
        self._calibrate_button.setEnabled(False)

        # Close any existing cameras first to release resources
        if self._left_camera or self._right_camera:
            self._close_cameras()
            # Give Windows time to release camera handles
            time.sleep(0.5)

        # Open cameras if serials are set
        if self._left_serial and self._right_serial:
            print(f"[CalibrationStep] Both serials set, calling _open_cameras()")
            self._open_cameras()
        else:
            print(f"[CalibrationStep] ERROR: Cannot open cameras - serials not set!")
            print(f"  Left: '{self._left_serial}' (set: {bool(self._left_serial)})")
            print(f"  Right: '{self._right_serial}' (set: {bool(self._right_serial)})")

        # Load previous alignment history
        self._load_alignment_history()

        # Auto-swap cameras based on history (if enabled)
        if self._auto_swap_on_startup and self._left_camera and self._right_camera:
            if self._check_camera_history():
                print("[Auto-Swap] Camera history indicates swap needed, performing automatic swap...")
                self._swap_left_right(save_to_history=False)  # Don't save yet, just swap
                print("[Auto-Swap] Cameras swapped based on historical data")

        # Start preview timer
        if self._left_camera and self._right_camera:
            print(f"[CalibrationStep] Starting preview timer (both cameras present)")
            self._preview_timer.start(33)  # ~30 FPS
        else:
            print(f"[CalibrationStep] WARNING: Not starting preview timer!")
            print(f"  Left camera: {self._left_camera}")
            print(f"  Right camera: {self._right_camera}")

    def on_exit(self) -> None:
        """Called when leaving step."""
        # Stop preview timer
        self._preview_timer.stop()

        # Close cameras
        self._close_cameras()

    def set_camera_serials(self, left_serial: str, right_serial: str) -> None:
        """Set camera serials from Step 1."""
        print(f"[CalibrationStep] set_camera_serials() called:")
        print(f"  Left serial: '{left_serial}'")
        print(f"  Right serial: '{right_serial}'")
        self._left_serial = left_serial
        self._right_serial = right_serial
        print(f"[CalibrationStep] Serials stored successfully")

    def _on_pattern_changed(self, value: int) -> None:
        """Handle pattern size change."""
        self._pattern_cols = self._pattern_cols_spin.value()
        self._pattern_rows = self._pattern_rows_spin.value()
        self._update_pattern_info()
        self._user_changed_pattern = True  # User manually changed, allow re-detection
        self._pattern_locked = False  # Unlock to allow new auto-detection
        print(f"[ChArUco Settings] Pattern manually changed to {self._pattern_cols}x{self._pattern_rows}")

    def _on_square_size_changed(self, value: float) -> None:
        """Handle square size change."""
        self._square_mm = value
        self._update_pattern_info()
        self._user_changed_pattern = True  # User manually changed, allow re-detection
        self._pattern_locked = False  # Unlock to allow new auto-detection
        print(f"[ChArUco Settings] Square size manually changed to {self._square_mm}mm")

    def _update_pattern_info(self) -> None:
        """Update the pattern info label."""
        lock_status = " 🔒 <b>LOCKED</b> (change settings to unlock)" if self._pattern_locked else " 🔓 Auto-detecting..."
        self._pattern_info.setText(
            f"<b>Looking for:</b> {self._pattern_cols}x{self._pattern_rows} ChArUco board with {self._square_mm:.0f}mm squares.{lock_status}<br>"
            f"<b>Stereo tip:</b> Board can be partially visible - ChArUco is robust to occlusion. "
            f"Move it to different positions and angles in the shared view area. Capture 10+ poses for good calibration."
        )

        # Update pattern info label with current detection
        if self._pattern_locked and self._cached_dict_name:
            dict_display = self._cached_dict_name.replace('DICT_', '').replace('_', ' ')
            self._pattern_info_label.setText(
                f"Detected: {self._pattern_cols}×{self._pattern_rows} ({dict_display})"
            )
            self._pattern_info_label.setStyleSheet("font-size: 9pt; color: #4CAF50; font-weight: bold;")
        elif self._cached_dict_name:
            dict_display = self._cached_dict_name.replace('DICT_', '').replace('_', ' ')
            self._pattern_info_label.setText(f"Scanning... ({dict_display})")
            self._pattern_info_label.setStyleSheet("font-size: 9pt; color: #FF9800;")
        else:
            self._pattern_info_label.setText("No pattern detected")
            self._pattern_info_label.setStyleSheet("font-size: 9pt; color: #666;")

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

    def _set_manual_rotation(self, camera: str, degrees: float) -> None:
        """Set manual rotation correction for a camera.

        Args:
            camera: "left" or "right"
            degrees: Rotation angle in degrees (positive = clockwise)
        """
        import yaml

        # Update config file
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("camera", {})

        if camera == "left":
            data["camera"]["rotation_left"] = float(degrees)
        else:
            data["camera"]["rotation_right"] = float(degrees)

        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Restart cameras if open to apply rotation
        if self._left_camera is not None or self._right_camera is not None:
            self._preview_timer.stop()
            self._close_cameras()
            QtCore.QTimer.singleShot(300, self._restart_cameras_after_flip)

    def _reset_all_corrections(self) -> None:
        """Reset all rotation and offset corrections to zero."""
        import yaml

        # Update config file
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("camera", {})

        # Reset all correction values
        data["camera"]["rotation_left"] = 0.0
        data["camera"]["rotation_right"] = 0.0
        data["camera"]["vertical_offset_px"] = 0

        # Clear alignment quality data
        if "alignment_quality" in data["camera"]:
            del data["camera"]["alignment_quality"]

        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Reset UI controls
        self._rotate_left_spin.setValue(0.0)
        self._rotate_right_spin.setValue(0.0)

        print("INFO: All rotation and offset corrections reset to zero")

        # Restart cameras if open to apply reset
        if self._left_camera is not None or self._right_camera is not None:
            self._preview_timer.stop()
            self._close_cameras()
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

    def _on_auto_detect_toggled(self, state: int) -> None:
        """Handle auto-detection checkbox toggle."""
        enabled = state == QtCore.Qt.CheckState.Checked.value

        if enabled:
            # Re-enable auto-detection
            self._pattern_locked = False
            print("[ChArUco] Auto-detection ENABLED - will detect board size automatically")
        else:
            # Disable auto-detection, use manual settings
            self._pattern_locked = True  # Lock prevents auto-detection
            print(f"[ChArUco] Auto-detection DISABLED - using manual settings: {self._pattern_cols}x{self._pattern_rows}, {self._square_mm}mm")

    def _auto_swap_cameras(self) -> None:
        """Intelligently swap cameras based on ChArUco marker positions.

        Analyzes the horizontal position of markers in both camera views.
        If left camera sees markers more on the right side and right camera
        sees markers more on the left side, they should be swapped.
        """
        if not self._left_camera or not self._right_camera:
            QtWidgets.QMessageBox.warning(
                self,
                "Cameras Not Ready",
                "Both cameras must be open to perform auto-swap.\n\n"
                "Please ensure both cameras are connected and showing previews."
            )
            return

        try:
            # Get current frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            if not left_frame or not right_frame:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Frame Capture Failed",
                    "Could not capture frames from cameras.\n\n"
                    "Please ensure both cameras are working properly."
                )
                return

            # Detect markers in both images
            left_marker_pos = self._get_marker_horizontal_position(left_frame.image)
            right_marker_pos = self._get_marker_horizontal_position(right_frame.image)

            if left_marker_pos is None or right_marker_pos is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Board Not Detected",
                    "Could not detect ChArUco board in both cameras.\n\n"
                    "Please:\n"
                    "1. Hold board in view of BOTH cameras\n"
                    "2. Ensure board is well-lit and in focus\n"
                    "3. Wait for 'READY' status on both cameras\n"
                    "4. Try again"
                )
                return

            # Determine if swap is needed
            # Left camera should see board on LEFT side of image (markers toward right)
            # Right camera should see board on RIGHT side of image (markers toward left)
            # If left camera's markers are on the right (> 0.5) and right camera's markers are on left (< 0.5), they're correct
            # If opposite, they need swapping

            should_swap = False
            explanation = ""
            confidence = 0.0

            # Calculate confidence based on how far markers are from center
            # Confidence increases as markers move away from center (0.5)
            left_deviation = abs(left_marker_pos - 0.5)
            right_deviation = abs(right_marker_pos - 0.5)
            avg_deviation = (left_deviation + right_deviation) / 2.0
            confidence = min(100, avg_deviation * 200)  # Scale to 0-100%

            if left_marker_pos > 0.6 and right_marker_pos < 0.4:
                # Correct orientation - left camera sees board toward right, right camera sees board toward left
                explanation = (
                    "Cameras are correctly positioned:\n\n"
                    f"Left camera sees board at {left_marker_pos:.1%} (toward right side) ✓\n"
                    f"Right camera sees board at {right_marker_pos:.1%} (toward left side) ✓\n\n"
                    f"Confidence: {confidence:.0f}%\n\n"
                    "No swap needed!"
                )
            elif left_marker_pos < 0.4 and right_marker_pos > 0.6:
                # Incorrect orientation - cameras need swapping
                should_swap = True
                explanation = (
                    "Cameras appear to be SWAPPED:\n\n"
                    f"Left camera sees board at {left_marker_pos:.1%} (toward left side) ✗\n"
                    f"Right camera sees board at {right_marker_pos:.1%} (toward right side) ✗\n\n"
                    f"Confidence: {confidence:.0f}%\n\n"
                    "Cameras will be swapped automatically."
                )
            else:
                # Ambiguous - board might be centered or detection unclear
                explanation = (
                    "Cannot determine camera orientation:\n\n"
                    f"Left camera sees board at {left_marker_pos:.1%}\n"
                    f"Right camera sees board at {right_marker_pos:.1%}\n\n"
                    f"Confidence: {confidence:.0f}% (too low for reliable detection)\n\n"
                    "Board appears centered or detection is unclear.\n\n"
                    "Tips:\n"
                    "• Move board more to one side\n"
                    "• Ensure board is clearly visible in both cameras\n"
                    "• Try manual swap if needed"
                )

            # Show results
            if should_swap:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Swap Cameras?",
                    explanation + "\n\nSwap cameras now?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                )

                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    self._swap_left_right()
                    QtWidgets.QMessageBox.information(
                        self,
                        "Cameras Swapped",
                        "Left and right cameras have been swapped.\n\n"
                        "The system will restart the cameras with the new assignment."
                    )
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Camera Orientation",
                    explanation
                )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Auto-Swap Error",
                f"Error during auto-swap detection:\n{str(e)}\n\n"
                "Please try manual swap if needed."
            )

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

        def get_focus_status(blur_score: float) -> tuple[str, str, str]:
            """Get focus status text, color, and background color.

            Returns:
                (status_text, text_color, background_color)
            """
            if blur_score >= EXCELLENT_THRESHOLD:
                return (f"Focus: Excellent ({blur_score:.0f})", "#FFFFFF", "#4CAF50")  # Green
            elif blur_score >= GOOD_THRESHOLD:
                return (f"Focus: Good ({blur_score:.0f})", "#000000", "#8BC34A")  # Light green
            elif blur_score >= POOR_THRESHOLD:
                return (f"Focus: Acceptable ({blur_score:.0f})", "#000000", "#FFC107")  # Yellow
            else:
                return (f"⚠ ADJUST FOCUS ⚠ ({blur_score:.0f})", "#FFFFFF", "#F44336")  # Red

        # Update left camera focus indicator
        left_text, left_color, left_bg = get_focus_status(left_blur)
        self._left_focus.setText(left_text)
        self._left_focus.setStyleSheet(
            f"font-size: 12pt; font-weight: bold; padding: 6px; "
            f"background-color: {left_bg}; color: {left_color}; border-radius: 3px;"
        )

        # Update right camera focus indicator
        right_text, right_color, right_bg = get_focus_status(right_blur)
        self._right_focus.setText(right_text)
        self._right_focus.setStyleSheet(
            f"font-size: 12pt; font-weight: bold; padding: 6px; "
            f"background-color: {right_bg}; color: {right_color}; border-radius: 3px;"
        )

        # Determine which camera needs adjustment (if any)
        if left_blur < POOR_THRESHOLD and right_blur < POOR_THRESHOLD:
            # Both cameras need adjustment
            print(f"[Focus] ⚠ BOTH CAMERAS need focus adjustment! Left: {left_blur:.0f}, Right: {right_blur:.0f}")
        elif left_blur < POOR_THRESHOLD:
            # Only left camera needs adjustment
            print(f"[Focus] ⚠ LEFT CAMERA needs focus adjustment! Score: {left_blur:.0f} (Right: {right_blur:.0f})")
        elif right_blur < POOR_THRESHOLD:
            # Only right camera needs adjustment
            print(f"[Focus] ⚠ RIGHT CAMERA needs focus adjustment! Score: {right_blur:.0f} (Left: {left_blur:.0f})")

    def _load_camera_history(self) -> dict:
        """Load historical camera position assignments.

        Returns:
            Dict mapping serial -> 'left' or 'right'
        """
        import json

        if not self._camera_history_file.exists():
            return {}

        try:
            with open(self._camera_history_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_camera_history(self):
        """Save current camera assignments to history."""
        import json

        history = self._load_camera_history()

        # Update with current assignments
        if self._left_serial:
            history[self._left_serial] = 'left'
        if self._right_serial:
            history[self._right_serial] = 'right'

        # Save
        try:
            self._camera_history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._camera_history_file, 'w') as f:
                json.dump(history, f, indent=2)
            print(f"[Camera History] Saved: {self._left_serial}=left, {self._right_serial}=right")
        except Exception as e:
            print(f"[Camera History] Failed to save: {e}")

    def _check_camera_history(self) -> bool:
        """Check if current cameras match historical assignments.

        Returns:
            True if cameras need swapping based on history
        """
        history = self._load_camera_history()

        if not history or not self._left_serial or not self._right_serial:
            return False

        # Check if serials are in history
        left_history = history.get(self._left_serial)
        right_history = history.get(self._right_serial)

        # If both cameras have history, check if they're swapped
        if left_history and right_history:
            if left_history == 'right' and right_history == 'left':
                print(f"[Camera History] Cameras appear SWAPPED based on history:")
                print(f"  {self._left_serial} was previously 'right' (now in left position)")
                print(f"  {self._right_serial} was previously 'left' (now in right position)")
                return True

        return False

    def _swap_left_right(self, save_to_history: bool = True) -> None:
        """Swap left and right camera assignments.

        Args:
            save_to_history: Whether to save the new assignment to history
        """
        import yaml

        # Swap the serial numbers
        self._left_serial, self._right_serial = self._right_serial, self._left_serial

        print(f"INFO: Swapped cameras - Left: {self._left_serial}, Right: {self._right_serial}")

        # Save to history
        if save_to_history:
            self._save_camera_history()

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
            print(f"[_open_cameras] Starting camera initialization")
            print(f"  Backend: '{self._backend}'")
            print(f"  Left serial: '{self._left_serial}'")
            print(f"  Right serial: '{self._right_serial}'")

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

                print(f"[OpenCV Backend] Extracting camera indices:")
                print(f"  Left serial: '{self._left_serial}'")
                print(f"  Right serial: '{self._right_serial}'")

                # Extract index from "Camera N" format or use serial directly if it's a number
                # Convert to integer for OpenCV
                if self._left_serial.isdigit():
                    left_index = int(self._left_serial)
                else:
                    left_index = int(self._left_serial.split()[-1])

                if self._right_serial.isdigit():
                    right_index = int(self._right_serial)
                else:
                    right_index = int(self._right_serial.split()[-1])

                print(f"  Extracted left index: {left_index} (type: {type(left_index)})")
                print(f"  Extracted right index: {right_index} (type: {type(right_index)})")

                self._left_camera = OpenCVCamera()
                self._right_camera = OpenCVCamera()

                # Open left camera
                try:
                    print(f"DEBUG: Opening left camera with index: {left_index} (flip={flip_left})")
                    self._left_camera.open(left_index)
                    print(f"DEBUG: Left camera opened successfully")
                except Exception as e:
                    print(f"ERROR: Failed to open left camera (index {left_index}): {e}")
                    import traceback
                    traceback.print_exc()
                    raise RuntimeError(f"Failed to open left camera at index {left_index}: {e}")

                # Open right camera
                try:
                    print(f"DEBUG: Opening right camera with index: {right_index} (flip={flip_right})")
                    self._right_camera.open(right_index)
                    print(f"DEBUG: Right camera opened successfully")
                except Exception as e:
                    print(f"ERROR: Failed to open right camera (index {right_index}): {e}")
                    import traceback
                    traceback.print_exc()
                    raise RuntimeError(f"Failed to open right camera at index {right_index}: {e}")

                # Configure cameras with settings from config including flip and rotation correction
                try:
                    print(f"DEBUG: Configuring left camera (width={width}, height={height}, fps={fps})")
                    self._left_camera.set_mode(width, height, fps, pixfmt, flip_180=flip_left, rotation_correction=rotation_left)
                    print(f"DEBUG: Left camera configured successfully")
                except Exception as e:
                    print(f"ERROR: Failed to configure left camera: {e}")
                    import traceback
                    traceback.print_exc()
                    raise RuntimeError(f"Failed to configure left camera: {e}")

                try:
                    print(f"DEBUG: Configuring right camera (width={width}, height={height}, fps={fps})")
                    self._right_camera.set_mode(width, height, fps, pixfmt, flip_180=flip_right, rotation_correction=rotation_right)
                    print(f"DEBUG: Right camera configured successfully")
                except Exception as e:
                    print(f"ERROR: Failed to configure right camera: {e}")
                    import traceback
                    traceback.print_exc()
                    raise RuntimeError(f"Failed to configure right camera: {e}")

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

            print(f"[CalibrationStep] Cameras opened successfully!")
            print(f"  Left camera object: {self._left_camera} (serial: {self._left_serial})")
            print(f"  Right camera object: {self._right_camera} (serial: {self._right_serial})")

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
            # Only log once to avoid spam
            if not hasattr(self, '_logged_missing_cameras'):
                print(f"[CalibrationStep] _update_preview() - missing cameras!")
                print(f"  Left camera: {self._left_camera}")
                print(f"  Right camera: {self._right_camera}")
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
                self._left_status.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; padding: 8px; "
                    "background-color: #4CAF50; color: #FFFFFF; border-radius: 5px;"
                )
            else:
                self._left_status.setText("⏳ Waiting for board...")
                self._left_status.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; padding: 8px; "
                    "background-color: #95a5a6; color: #FFFFFF; border-radius: 5px;"
                )

            if right_detected:
                self._right_status.setText("✅ READY")
                self._right_status.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; padding: 8px; "
                    "background-color: #4CAF50; color: #FFFFFF; border-radius: 5px;"
                )
            else:
                self._right_status.setText("⏳ Waiting for board...")
                self._right_status.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; padding: 8px; "
                    "background-color: #95a5a6; color: #FFFFFF; border-radius: 5px;"
                )

            # Update focus quality indicators
            self._update_focus_indicators(left_blur, right_blur)

            # Enable capture if both detected
            self._capture_button.setEnabled(left_detected and right_detected)

        except Exception:
            pass

    def _auto_detect_charuco_pattern(self, marker_ids: np.ndarray) -> Optional[tuple[int, int, float]]:
        """Auto-detect ChArUco pattern size and calculate square size.

        Assumes board is printed vertically on standard US letter paper (8.5" x 11").

        Args:
            marker_ids: Detected ArUco marker IDs

        Returns:
            (cols, rows, square_mm) tuple or None if cannot detect
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

        # Calculate square size assuming US letter paper (215.9mm x 279.4mm) vertical orientation
        # Board uses approximately 70-75% of paper height
        LETTER_HEIGHT_MM = 279.4
        USABLE_HEIGHT_RATIO = 0.70  # Board uses ~70% of paper

        # For N rows, board height = N * square_size
        board_height_mm = LETTER_HEIGHT_MM * USABLE_HEIGHT_RATIO
        square_mm = board_height_mm / rows

        # Round to nearest 0.5mm for cleaner values
        square_mm = round(square_mm * 2) / 2

        print(f"  Detected {len(marker_ids)} markers (max_id={max_id})")
        print(f"  Inferred pattern: {cols}x{rows}")
        print(f"  Calculated square size: {square_mm:.1f}mm (assuming letter paper vertical)")

        return (cols, rows, square_mm)

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
            ('DICT_6X6_250', cv2.aruco.DICT_6X6_250),
            ('DICT_5X5_250', cv2.aruco.DICT_5X5_250),
            ('DICT_4X4_250', cv2.aruco.DICT_4X4_250),
            ('DICT_6X6_100', cv2.aruco.DICT_6X6_100),
            ('DICT_5X5_100', cv2.aruco.DICT_5X5_100),
            ('DICT_4X4_100', cv2.aruco.DICT_4X4_100),
            ('DICT_6X6_50', cv2.aruco.DICT_6X6_50),      # Calib.io might use this
            ('DICT_5X5_50', cv2.aruco.DICT_5X5_50),      # Calib.io might use this
            ('DICT_4X4_50', cv2.aruco.DICT_4X4_50),
            ('DICT_ARUCO_ORIGINAL', cv2.aruco.DICT_ARUCO_ORIGINAL),
        ]

        # Increment frame counter
        self._dict_scan_counter += 1

        # Only rescan all dictionaries every 60 frames (~2 seconds at 30fps) or if no cached dict
        if self._cached_dict_name is None or self._dict_scan_counter >= 60:
            self._dict_scan_counter = 0

            best_marker_corners = None
            best_marker_ids = None
            best_rejected = None
            best_dict_name = 'DICT_6X6_250'
            best_marker_count = 0

            # Log only on full scan
            if self._detection_log_counter % 10 == 0:
                print(f"[ChArUco Detection] Scanning {len(DICTIONARIES_TO_TRY)} dictionaries...")

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
            dict_changed = (self._cached_dict_name != best_dict_name)
            if dict_changed and best_marker_count > 0:
                print(f"[ChArUco Detection] *** DICTIONARY CHANGED: {self._cached_dict_name or 'None'} -> {best_dict_name} ***")
                print(f"[ChArUco Detection] Detected {best_marker_count} markers with {best_dict_name}")

            self._cached_dict_name = best_dict_name
            marker_corners = best_marker_corners
            marker_ids = best_marker_ids
            rejected = best_rejected

            # Log only occasionally
            if self._detection_log_counter % 10 == 0:
                num_detected = len(marker_ids) if marker_ids is not None else 0
                num_rejected = len(rejected) if rejected is not None and len(rejected) > 0 else 0
                print(f"[ChArUco Detection] Using {best_dict_name}: {num_detected} markers detected, {num_rejected} rejected")
        else:
            # Use cached dictionary for fast detection
            dict_id = next(d[1] for d in DICTIONARIES_TO_TRY if d[0] == self._cached_dict_name)
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
        best_dict_name = self._cached_dict_name if self._cached_dict_name else 'DICT_6X6_250'

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
                cv2.putText(annotated, "Tried all common ArUco dictionaries - none matched", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
                cv2.putText(annotated, "Possible causes: Wrong print scale, damaged print, glare/shadows", (10, 115),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
            else:
                hint_text = "Move ChArUco board into view"
                cv2.putText(annotated, hint_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # Show blur warning if image is blurry
            if is_blurry:
                cv2.putText(annotated, f"WARNING: Image blurry! (score={blur_score:.0f})", (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                cv2.putText(annotated, "Try: Adjust camera focus, better lighting", (10, 150),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)

            # FALLBACK: Try plain checkerboard detection if ChArUco markers failed
            print("[Calibration] ChArUco markers not detected, trying plain checkerboard fallback...")
            try:
                fallback_result = self._try_checkerboard_fallback(gray, annotated, blur_score, is_blurry)
                if fallback_result is not None:
                    return fallback_result  # Returns (True, annotated_image, blur_score)
            except Exception as e:
                print(f"[Calibration] Checkerboard fallback threw exception: {e}")

            return False, annotated, blur_score

        # Log which markers were found (reduced frequency)
        if self._detection_log_counter % 30 == 0:
            marker_id_list = marker_ids.flatten().tolist() if marker_ids is not None else []
            print(f"[ChArUco Detection] Marker IDs found: {marker_id_list}")

        # AUTO-DETECT: Try to infer pattern size from detected markers
        # Only run if pattern not locked (user can unlock by manually changing settings)
        import time
        current_time = time.time()

        # Auto-detect pattern only if checkbox is enabled and pattern not locked
        if (self._auto_detect_pattern_checkbox.isChecked() and
            not self._pattern_locked and
            current_time - self._last_auto_detect_time >= 3.0):
            auto_detected_pattern = self._auto_detect_charuco_pattern(marker_ids)
            if auto_detected_pattern:
                auto_cols, auto_rows, auto_square_mm = auto_detected_pattern
                # Update if different from current settings
                if (auto_cols != self._pattern_cols or auto_rows != self._pattern_rows or
                    abs(auto_square_mm - self._square_mm) > 0.5):
                    print(f"[ChArUco Detection] AUTO-DETECTED: Pattern {auto_cols}x{auto_rows}, square={auto_square_mm:.1f}mm - LOCKING")
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
                    print(f"[ChArUco Detection] Pattern LOCKED at {auto_cols}x{auto_rows}. Change settings to unlock.")

                    # Store detected pattern for multi-pattern support
                    pattern_info = {
                        'cols': auto_cols,
                        'rows': auto_rows,
                        'square_mm': auto_square_mm,
                        'dictionary': self._cached_dict_name or 'DICT_6X6_250'
                    }
                    # Add to list if not already present
                    if pattern_info not in self._detected_patterns:
                        self._detected_patterns.append(pattern_info)
                        print(f"[Multi-Pattern] Stored pattern: {pattern_info}")

        # Draw detected markers in green
        cv2.aruco.drawDetectedMarkers(annotated, marker_corners, marker_ids)

        # Create ChArUco board
        try:
            # Try newer API first (OpenCV 4.7+)
            board = cv2.aruco.CharucoBoard(
                (self._pattern_cols, self._pattern_rows),
                self._square_mm,
                self._square_mm * 0.75,  # Marker size is 75% of square
                aruco_dict
            )
        except (AttributeError, TypeError):
            # Fall back to older API
            board = cv2.aruco.CharucoBoard_create(
                self._pattern_cols,
                self._pattern_rows,
                self._square_mm,
                self._square_mm * 0.75,
                aruco_dict
            )

        # Interpolate ChArUco corners
        # Log only occasionally to avoid spam
        if self._detection_log_counter % 30 == 0:
            print(f"[ChArUco Detection] Creating board {self._pattern_cols}x{self._pattern_rows}, square={self._square_mm}mm, marker={self._square_mm*0.75}mm")
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
        diag_text = f"Markers: {num_markers} (Rejected: {num_rejected}) | Corners: {corner_count} | Blur: {blur_score:.0f}"
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
        cv2.putText(annotated, full_text, (10, gray.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

        if num_corners is not None and num_corners >= MIN_CORNERS:
            # Draw ChArUco corners
            cv2.aruco.drawDetectedCornersCharuco(annotated, charuco_corners, charuco_ids, (0, 255, 0))

            # Add success indicator with background
            success_text = f"READY - {num_corners} corners detected"
            text_size = cv2.getTextSize(success_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 128, 0), -1)
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 255, 0), 2)
            cv2.putText(annotated, success_text, (10, 75),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Warn if blurry even though detected
            if is_blurry:
                cv2.putText(annotated, "WARNING: Blurry - may affect calibration", (10, 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

            return True, annotated, blur_score
        else:
            # Not enough corners detected - provide detailed diagnostics
            corner_count = num_corners if num_corners is not None else 0
            error_text = f"Need {MIN_CORNERS}+ corners (found {corner_count})"
            text_size = cv2.getTextSize(error_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 0, 128), -1)
            cv2.rectangle(annotated, (5, 50), (text_size[0] + 15, 85), (0, 165, 255), 2)
            cv2.putText(annotated, error_text, (10, 75),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Provide specific suggestions based on detection state
            y_offset = 105
            if is_blurry:
                cv2.putText(annotated, "ISSUE: Image is blurry - adjust camera focus!", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                y_offset += 30

            if num_markers < 4:
                cv2.putText(annotated, f"ISSUE: Only {num_markers} markers detected (need more)", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                cv2.putText(annotated, "Try: Move board closer, better lighting, sharper focus", (10, y_offset + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
            else:
                cv2.putText(annotated, f"Markers OK ({num_markers} found), but corners failed", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                cv2.putText(annotated, "Try: Ensure full board visible, check pattern size", (10, y_offset + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)

            # FALLBACK: Try plain checkerboard detection if ChArUco corner interpolation failed
            print(f"[Calibration] ChArUco found {num_markers} markers but only {corner_count} corners, trying checkerboard fallback...")
            try:
                fallback_result = self._try_checkerboard_fallback(gray, annotated, blur_score, is_blurry)
                if fallback_result is not None:
                    return fallback_result  # Returns (True, annotated_image, blur_score)
            except Exception as e:
                print(f"[Calibration] Checkerboard fallback threw exception: {e}")

            return False, annotated, blur_score

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
                print("[Checkerboard Fallback] Invalid input images")
                return None

            # Checkerboard has (cols-1, rows-1) internal corners
            board_size = (self._pattern_cols - 1, self._pattern_rows - 1)

            # Try to find checkerboard corners
            # flags: Use adaptive threshold + normalize image for better detection
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE

            ret, corners = cv2.findChessboardCorners(gray, board_size, flags)

            if not ret or corners is None:
                print(f"[Checkerboard Fallback] Failed to detect {board_size} checkerboard pattern")
                return None

            # Refine corner locations to sub-pixel accuracy
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            # Draw detected corners
            cv2.drawChessboardCorners(annotated, board_size, corners_refined, ret)

            num_corners = len(corners_refined)
            print(f"[Checkerboard Fallback] SUCCESS! Detected {num_corners} corners using plain checkerboard mode")

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
            print(f"[Checkerboard Fallback] ERROR: {e}")
            import traceback
            traceback.print_exc()
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

            # Update UI - Both progress bar and label
            count = len(self._captures)
            self._capture_progress_bar.setValue(count)

            if count < self._min_captures:
                self._capture_count_label.setText(f"Progress: {count}/{self._min_captures} poses captured")
                self._capture_count_label.setStyleSheet(
                    "font-size: 12pt; font-weight: bold; color: #d32f2f;"
                )
            else:
                self._capture_count_label.setText(f"Progress: {count}/{self._min_captures} poses ✓ Ready!")
                self._capture_count_label.setStyleSheet(
                    "font-size: 12pt; font-weight: bold; color: #388e3c;"
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
                self._capture_count_label.setText(f"Progress: 0/{self._min_captures} poses captured")
                self._capture_count_label.setStyleSheet(
                    "font-size: 12pt; font-weight: bold; color: #d32f2f;"
                )
                self._capture_progress_bar.setValue(0)
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
            <div style='font-size: 11pt; color: #000000; font-weight: bold;'>{results.quality}</div>
            <div style='font-size: 10pt; color: #000000;'>
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
