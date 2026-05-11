"""Secondary panel builders for the calibration step."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.services.tooling import get_tooling_service
from capture import CameraDevice
from contracts.tooling import CalibrationRequest
from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)
from log_config.logger import get_logger
from ui.setup.steps.calibration_errors import build_calibration_error_payload
from ui.setup.steps.calibration_worker import CalibrationWorker
from ui.themes import (
    apply_standard_layout,
    ask_confirmation,
    build_notice,
    get_style_manager,
    polish_form_controls,
    show_choice_dialog,
    show_message_dialog,
    style_message_panel,
    style_preview_surface,
    style_progress_bar,
    style_status_label,
)

logger = get_logger(__name__)


class CalibrationStepPanelsMixin:
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
        self._auto_detect_pattern_checkbox.stateChanged.connect(self._on_auto_detect_toggled)

        # Pattern detection info label
        self._pattern_info_label = QtWidgets.QLabel("No pattern detected")
        self._pattern_info_label.setToolTip("Shows currently detected ChArUco pattern and dictionary")
        if self._charuco_metadata_path is not None:
            self._set_pattern_info_state(
                f"Loaded board metadata: {self._pattern_cols}x{self._pattern_rows}, {self._square_mm:.1f} mm",
                "success",
            )
            self._pattern_locked = True
        else:
            self._set_pattern_info_state("No pattern detected", "info")

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
        self._flip_left_btn.setText("Flip Left 180")
        self._flip_right_btn.setText("Flip Right 180")
        self._style_manager.style_button(self._flip_left_btn, "ghost")
        self._style_manager.style_button(self._flip_right_btn, "ghost")

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
        self._reset_corrections_btn.setText("Reset All")
        self._style_manager.style_button(self._reset_corrections_btn, "ghost")

        # Auto-correction checkbox
        self._auto_correct_checkbox = QtWidgets.QCheckBox("Auto-apply alignment corrections")
        self._auto_correct_checkbox.setChecked(False)  # OFF by default
        self._auto_correct_checkbox.setToolTip(
            "When enabled, automatically apply software corrections for camera rotation and vertical offset.\n"
            "When disabled, alignment is checked but corrections are NOT applied automatically.\n"
            "You can manually apply corrections using the alignment widget buttons.\n\n"
            "Recommendation: Keep OFF unless you understand the alignment diagnostics."
        )
        # Swap L/R button (manual)
        self._swap_lr_btn = QtWidgets.QPushButton("🔄 Swap L/R")
        self._swap_lr_btn.setToolTip("Manually swap left and right camera assignments")
        self._swap_lr_btn.clicked.connect(self._swap_left_right)
        self._swap_lr_btn.setText("Swap Left / Right")
        self._style_manager.style_button(self._swap_lr_btn, "ghost")

        # Auto-swap button (intelligent swap based on marker positions)
        self._auto_swap_btn = QtWidgets.QPushButton("🔍 Auto-Swap")
        self._auto_swap_btn.setToolTip(
            "Intelligently detect which camera should be left/right\n"
            "based on ChArUco marker positions.\n\n"
            "Hold board in view of both cameras and click this button.\n"
            "System will analyze marker positions and swap if needed."
        )
        self._auto_swap_btn.clicked.connect(self._auto_swap_cameras)
        self._auto_swap_btn.setText("Auto-Swap")
        self._style_manager.style_button(self._auto_swap_btn, "success")

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
            status_tip = "This value was calculated by stereo calibration (more accurate than manual measurement)"
        else:
            status_text = f"({baseline_inches:.1f} in) ✏️ Manual"
            status_tip = "This is a manually entered value. Run calibration to get a precise measurement."

        self._baseline_inches_label = QtWidgets.QLabel(status_text)
        self._baseline_inches_label.setToolTip(status_tip)
        self._set_baseline_state(
            f"{baseline_inches:.1f} in · {'Calibrated' if is_calibrated else 'Manual'}",
            "info" if is_calibrated else "warning",
            status_tip,
        )

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
        self._set_alignment_state("Checking alignment...", "info")

        # Wrap in scroll area to limit height
        status_scroll = QtWidgets.QScrollArea()
        status_scroll.setWidget(self._alignment_status_label)
        status_scroll.setWidgetResizable(True)
        status_scroll.setMinimumHeight(100)  # Minimum height to show content
        status_scroll.setMaximumHeight(200)  # Increased from 150px to show more issues
        status_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        layout.addWidget(status_scroll)

        # NEW: Quality gauge (visual score indicator)
        self._quality_gauge = QtWidgets.QLabel()
        self._quality_gauge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._set_quality_gauge_state("", "info")
        self._quality_gauge.hide()
        layout.addWidget(self._quality_gauge)

        # Details (hidden by default, shown after check)
        self._alignment_details = QtWidgets.QLabel()
        self._alignment_details.setWordWrap(True)
        style_message_panel(self._alignment_details, "info")
        self._alignment_details.hide()
        layout.addWidget(self._alignment_details)

        # NEW: Directional Guidance (hidden by default)
        self._guidance_label = QtWidgets.QLabel()
        self._guidance_label.setWordWrap(True)
        style_message_panel(self._guidance_label, "warning")
        self._guidance_label.hide()
        layout.addWidget(self._guidance_label)

        # NEW: Predicted Calibration Quality (hidden by default)
        self._prediction_label = QtWidgets.QLabel()
        self._prediction_label.setWordWrap(True)
        style_message_panel(self._prediction_label, "success")
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
        style_message_panel(self._history_list, "info")
        history_layout.addWidget(self._history_list)

        self._history_group.setLayout(history_layout)
        self._history_group.hide()
        layout.addWidget(self._history_group)

        # Buttons row (hidden by default)
        buttons_layout = QtWidgets.QHBoxLayout()

        self._recheck_alignment_btn = QtWidgets.QPushButton("🔄 Full Check")
        self._recheck_alignment_btn.setToolTip("Run full alignment check (averaged over 10 frames, ~1 second)")
        self._recheck_alignment_btn.clicked.connect(self._run_automatic_alignment_check)
        self._recheck_alignment_btn.setText("Full Check")
        self._style_manager.style_button(self._recheck_alignment_btn, "primary")
        self._recheck_alignment_btn.hide()

        self._quick_check_btn = QtWidgets.QPushButton("⚡ Quick Check")
        self._quick_check_btn.setToolTip("Run quick alignment check (1 frame, <100ms)")
        self._quick_check_btn.clicked.connect(self._run_quick_alignment_check)
        self._quick_check_btn.setText("Quick Check")
        self._style_manager.style_button(self._quick_check_btn, "ghost")
        self._quick_check_btn.hide()

        self._alignment_details_btn = QtWidgets.QPushButton("📊 Details")
        self._alignment_details_btn.setToolTip("Show detailed alignment report")
        self._alignment_details_btn.clicked.connect(self._show_alignment_details)
        self._alignment_details_btn.setText("Details")
        self._style_manager.style_button(self._alignment_details_btn, "ghost")
        self._alignment_details_btn.hide()

        self._show_features_btn = QtWidgets.QPushButton("👁 Show Features")
        self._show_features_btn.setToolTip("Visualize matched features on camera previews")
        self._show_features_btn.clicked.connect(self._show_feature_overlay)
        self._show_features_btn.setText("Show Features")
        self._style_manager.style_button(self._show_features_btn, "ghost")
        self._show_features_btn.hide()

        self._export_report_btn = QtWidgets.QPushButton("📄 Export Report")
        self._export_report_btn.setToolTip("Export alignment report as HTML")
        self._export_report_btn.clicked.connect(self._export_alignment_report)
        self._export_report_btn.setText("Export Report")
        self._style_manager.style_button(self._export_report_btn, "ghost")
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
        self._save_preset_btn.setText("Save Preset")
        self._style_manager.style_button(self._save_preset_btn, "ghost")
        self._save_preset_btn.hide()

        self._load_preset_btn = QtWidgets.QPushButton("📂 Load Preset")
        self._load_preset_btn.setToolTip("Load a saved alignment preset")
        self._load_preset_btn.clicked.connect(self._load_alignment_preset)
        self._load_preset_btn.setText("Load Preset")
        self._style_manager.style_button(self._load_preset_btn, "ghost")
        self._load_preset_btn.hide()

        self._compare_preset_btn = QtWidgets.QPushButton("⚖️ Compare")
        self._compare_preset_btn.setToolTip("Compare current alignment with saved preset")
        self._compare_preset_btn.clicked.connect(self._compare_with_preset)
        self._compare_preset_btn.setText("Compare")
        self._style_manager.style_button(self._compare_preset_btn, "ghost")
        self._compare_preset_btn.hide()

        preset_layout.addWidget(self._save_preset_btn)
        preset_layout.addWidget(self._load_preset_btn)
        preset_layout.addWidget(self._compare_preset_btn)
        preset_layout.addStretch()
        layout.addLayout(preset_layout)

        group.setLayout(layout)
        return group
