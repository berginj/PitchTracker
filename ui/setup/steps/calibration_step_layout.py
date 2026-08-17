"""Primary layout construction for the calibration step."""

from __future__ import annotations

from ui.setup.steps.calibration_step_mixin_host import CalibrationStepMixinHost


from PySide6 import QtCore, QtWidgets

from log_config.logger import get_logger
from ui.themes import (
    apply_standard_layout,
    build_notice,
    polish_form_controls,
    style_message_panel,
    style_preview_surface,
    style_progress_bar,
)

logger = get_logger(__name__)


class CalibrationStepLayoutMixin(CalibrationStepMixinHost):
    def _build_ui(self) -> None:
        """Build simplified calibration step UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Simple instruction at top
        self._instruction_label = QtWidgets.QLabel("<b style='font-size: 14pt;'>📷 Capture 10+ ChArUco Board Poses</b>")
        self._instruction_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._instruction_label.setText("Capture 10+ ChArUco Board Poses")
        style_message_panel(self._instruction_label, "info")
        layout.addWidget(self._instruction_label)

        # Camera type and calibration mode section
        mode_layout = QtWidgets.QHBoxLayout()

        # Camera type indicator
        camera_type_group = QtWidgets.QGroupBox("Camera Type")
        camera_type_layout = QtWidgets.QVBoxLayout()
        self._camera_type_label = QtWidgets.QLabel("Detecting...")
        self._camera_stability_label = QtWidgets.QLabel("Stability: --/100")
        self._set_camera_type_state("Detecting...", "info")
        self._set_camera_stability_state("Stability: --/100", "info")
        camera_type_layout.addWidget(self._camera_type_label)
        camera_type_layout.addWidget(self._camera_stability_label)
        camera_type_group.setLayout(camera_type_layout)
        mode_layout.addWidget(camera_type_group, 1)

        # Calibration mode selection
        mode_group = QtWidgets.QGroupBox("Calibration Mode")
        mode_select_layout = QtWidgets.QVBoxLayout()

        self._quick_radio = QtWidgets.QRadioButton("Quick (3-5 min, 90-95% accuracy)")
        self._full_radio = QtWidgets.QRadioButton("Full (10-15 min, best accuracy)")
        self._full_radio.setChecked(True)  # Default to full mode

        self._quick_radio.toggled.connect(self._on_mode_changed)
        self._full_radio.toggled.connect(self._on_mode_changed)

        mode_select_layout.addWidget(self._quick_radio)
        mode_select_layout.addWidget(self._full_radio)
        mode_group.setLayout(mode_select_layout)
        mode_layout.addWidget(mode_group, 1)

        layout.addLayout(mode_layout)

        # Webcam warning banner (hidden by default)
        self._webcam_warning, self._webcam_warning_label = build_notice("", tone="warning")
        self._webcam_warning.hide()  # Hidden until webcam detected
        layout.addWidget(self._webcam_warning)

        # Progress bar showing captures
        progress_layout = QtWidgets.QHBoxLayout()
        self._capture_count_label = QtWidgets.QLabel("Progress: 0/10 poses captured")
        self._set_capture_progress_state(0, ready=False)

        self._capture_progress_bar = QtWidgets.QProgressBar()
        self._capture_progress_bar.setMinimum(0)
        self._capture_progress_bar.setMaximum(10)
        self._capture_progress_bar.setValue(0)
        self._capture_progress_bar.setFormat("%v/%m")
        self._capture_progress_bar.setMinimumHeight(30)
        style_progress_bar(self._capture_progress_bar, "success")

        progress_layout.addWidget(self._capture_count_label, 1)
        progress_layout.addWidget(self._capture_progress_bar, 3)
        layout.addLayout(progress_layout)

        # Camera previews (LARGE - 80% of screen)
        preview_layout = QtWidgets.QHBoxLayout()

        # Left preview
        left_group = QtWidgets.QGroupBox()
        left_group.setTitle("")  # No title for cleaner look
        self._left_view = QtWidgets.QLabel("No preview")
        self._left_view.setMinimumSize(200, 150)
        self._left_view.setScaledContents(True)
        self._left_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_preview_surface(self._left_view)

        # Simple status - just READY or NOT READY
        self._left_status = QtWidgets.QLabel("⏳ Waiting for board...")
        self._left_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._set_detection_status(self._left_status, detected=False)

        # Focus quality indicator
        self._left_focus = QtWidgets.QLabel("Focus: Unknown")
        self._left_focus.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._set_focus_status(self._left_focus, "Focus: Unknown", "info")

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
        self._right_view.setMinimumSize(200, 150)
        self._right_view.setScaledContents(True)
        self._right_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_preview_surface(self._right_view)

        # Simple status - just READY or NOT READY
        self._right_status = QtWidgets.QLabel("⏳ Waiting for board...")
        self._right_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._set_detection_status(self._right_status, detected=False)

        # Focus quality indicator
        self._right_focus = QtWidgets.QLabel("Focus: Unknown")
        self._right_focus.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._set_focus_status(self._right_focus, "Focus: Unknown", "info")

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

        self._capture_button = QtWidgets.QPushButton("Capture Pose")
        self._capture_button.setMinimumHeight(self._style_manager.theme.button_height_lg)
        self._capture_button.setMinimumWidth(200)
        self._capture_button.setEnabled(False)
        self._style_manager.style_button(self._capture_button, "success")
        self._capture_button.clicked.connect(self._capture_image_pair)

        self._calibrate_button = QtWidgets.QPushButton("Run Calibration")
        self._calibrate_button.setMinimumHeight(self._style_manager.theme.button_height_lg)
        self._calibrate_button.setMinimumWidth(200)
        self._calibrate_button.setEnabled(False)
        self._style_manager.style_button(self._calibrate_button, "primary")
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
        advanced_group.setTitle("Advanced Settings")
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
        self._release_button.setText("Force Release Cameras")
        self._style_manager.style_button(self._release_button, "danger")
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
        style_progress_bar(self._progress_bar, "default")
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # Results display
        self._results_text = QtWidgets.QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setMaximumHeight(100)
        style_message_panel(self._results_text, "info")
        self._results_text.hide()
        layout.addWidget(self._results_text)

        # Wrap entire layout in scroll area for accessibility
        scroll_content = QtWidgets.QWidget()
        scroll_content.setLayout(layout)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)
        polish_form_controls(self)
