"""Main window class for PitchTracker application."""

from __future__ import annotations

import json
import os
import platform
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml
from PySide6 import QtCore, QtGui, QtWidgets

from app.services.orchestrator import PipelineOrchestrator
from calib.plate_plane import estimate_and_write
from configs.app_state import load_state, save_state
from configs.lane_io import load_lane_rois, save_lane_rois
from configs.location_profiles import apply_profile, list_profiles, load_profile, save_profile
from configs.pitchers import add_pitcher, load_pitchers
from configs.roi_io import load_rois, save_rois
from configs.settings import load_config
from contracts import Frame, StereoObservation
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
from detect.lane import LaneRoi
from metrics.strike_zone import build_strike_zone
from exceptions import ConfigValidationError
from ui.dialogs import (
    CalibrationGuide,
    CalibrationWizardDialog,
    ChecklistDialog,
    DetectorSettingsDialog,
    PlatePlaneDialog,
    QuickCalibrateDialog,
    RecordingSettingsDialog,
    StartupDialog,
    StrikeZoneSettingsDialog,
)
from ui.drawing import frame_to_pixmap
from ui.geometry import (
    Overlay,
    Rect,
    normalize_rect,
    polygon_to_rect,
    rect_to_polygon,
    roi_overlays,
)
from ui.widgets import PlateMapWidget, RoiLabel
from ui.controllers import (
    CalibrationManager,
    CalibrationOverlayController,
    CaptureController,
    DeviceManager,
    ExportManager,
    FocusMonitorController,
    GameVisualizer,
    ProfileManager,
    RecordingController,
    ReplayController,
    RoiManager,
    SettingsManager,
)
from ui.themes import GlassButton, apply_standard_layout, ask_confirmation, get_style_manager, show_message_dialog

# System hardening imports
from app.events import get_error_bus, ErrorCategory, ErrorSeverity
from app.events.recovery import get_recovery_manager
from app.monitoring import get_resource_monitor
from app.lifecycle import get_cleanup_manager
from app.validation import ConfigValidator
from app.config import ResourceLimits, set_resource_limits
from app.ui.error_notification import ErrorNotificationWidget, ErrorNotificationBridge
from log_config.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, backend: str, config_path: Path) -> None:
        super().__init__()

        # Get git commit hash for version display
        git_commit = self._get_git_commit()
        version_str = f"v{APP_VERSION}"
        if git_commit:
            version_str += f" ({git_commit})"

        self.setWindowTitle(f"Pitch Tracker {version_str}")
        self._config_path_value = Path(config_path)

        # Validate configuration before loading (Phase 4)
        self._validate_config_at_startup(self._config_path_value)

        # Load configuration
        self._config = load_config(self._config_path_value)

        # Initialize system hardening (Phase 2-4)
        self._init_error_handling()
        self._init_resource_monitoring()
        self._init_resource_limits()

        self._service = PipelineOrchestrator(backend=backend)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_preview)
        self._roi_path = Path("rois/shared_rois.json")
        self._lane_path = Path("rois/shared_lane_rois.json")
        # Note: ROI state now managed by RoiManager
        # Note: Replay state now managed by ReplayController
        # Note: _pitcher_name and _location_profile now managed by ProfileManager
        # Note: Target/fiducial overlay state now managed by CalibrationOverlayController
        # Note: Focus peak tracking now managed by FocusMonitorController

        self._left_input = QtWidgets.QComboBox()
        self._right_input = QtWidgets.QComboBox()
        self._left_input.setEditable(True)
        self._right_input.setEditable(True)
        self._left_input.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self._right_input.setInsertPolicy(QtWidgets.QComboBox.NoInsert)

        self._start_button = QtWidgets.QPushButton("Start Capture")
        self._stop_button = QtWidgets.QPushButton("Stop Capture")
        self._restart_button = QtWidgets.QPushButton("Restart Capture")
        self._record_button = QtWidgets.QPushButton("Start Recording")
        self._stop_record_button = QtWidgets.QPushButton("Stop Recording")
        self._refresh_button = QtWidgets.QPushButton("Refresh Devices")
        self._replay_button = QtWidgets.QPushButton("Replay Video")
        self._pause_button = QtWidgets.QPushButton("Pause")
        self._step_button = QtWidgets.QPushButton("Step")
        self._training_button = QtWidgets.QPushButton("Training Capture")
        self._record_settings_button = QtWidgets.QPushButton("Recording Settings")
        self._strike_settings_button = QtWidgets.QPushButton("Strike Zone Settings")
        self._detector_settings_button = QtWidgets.QPushButton("Detector Settings")
        self._session_name = QtWidgets.QLineEdit()
        self._session_name.setPlaceholderText("Session name")
        self._profile_combo = QtWidgets.QComboBox()
        self._profile_combo.setPlaceholderText("Location profile")
        self._profile_load = QtWidgets.QPushButton("Load Profile")
        self._profile_save = QtWidgets.QPushButton("Save Profile")
        self._profile_name = QtWidgets.QLineEdit()
        self._profile_name.setPlaceholderText("New profile name")
        self._pitcher_combo = QtWidgets.QComboBox()
        self._pitcher_combo.setPlaceholderText("Pitcher")
        self._pitcher_add = QtWidgets.QPushButton("Add Pitcher")
        self._pitcher_name_input = QtWidgets.QLineEdit()
        self._pitcher_name_input.setPlaceholderText("New pitcher name")
        self._low_perf_button = QtWidgets.QPushButton("Low Perf Mode")
        self._cue_card_button = QtWidgets.QPushButton("Cue Card Test")
        self._enter_button = QtWidgets.QPushButton("Enter App")
        self._checklist_button = QtWidgets.QPushButton("Checklist")
        self._output_dir = QtWidgets.QLineEdit()
        self._output_dir.setPlaceholderText("Output dir")
        self._output_browse = QtWidgets.QPushButton("Browse")
        self._manual_speed = QtWidgets.QDoubleSpinBox()
        self._manual_speed.setMinimum(0.0)
        self._manual_speed.setMaximum(130.0)
        self._manual_speed.setSuffix(" mph")
        self._status_label = QtWidgets.QLabel("Idle")
        sm = get_style_manager()
        sm.style_status_indicator(self._status_label, "info")
        self._ball_combo = QtWidgets.QComboBox()
        self._ball_combo.addItems(["baseball", "softball"])
        self._batter_height = QtWidgets.QDoubleSpinBox()
        self._batter_height.setMinimum(40.0)
        self._batter_height.setMaximum(96.0)
        self._batter_height.setSuffix(" in")
        self._top_ratio = QtWidgets.QDoubleSpinBox()
        self._bottom_ratio = QtWidgets.QDoubleSpinBox()
        for ratio in (self._top_ratio, self._bottom_ratio):
            ratio.setMinimum(0.0)
            ratio.setMaximum(1.0)
            ratio.setSingleStep(0.01)
        self._save_strike_button = QtWidgets.QPushButton("Save Strike Zone")
        self._health_left = QtWidgets.QLabel("L: fps=0.0 jitter=0.0ms drops=0")
        sm.style_label(self._health_left, "status")
        self._health_right = QtWidgets.QLabel("R: fps=0.0 jitter=0.0ms drops=0")
        sm.style_label(self._health_right, "status")
        self._calib_summary = QtWidgets.QLabel("Calib: baseline_ft=? f_px=?")
        sm.style_label(self._calib_summary, "status")
        self._focus_left = QtWidgets.QLabel("L Focus: --- (peak: ---)")
        sm.style_label(self._focus_left, "status")
        self._focus_right = QtWidgets.QLabel("R Focus: --- (peak: ---)")
        sm.style_label(self._focus_right, "status")

        # Initialize focus monitor and calibration overlay controllers
        self._focus_monitor = FocusMonitorController(
            focus_left_label=self._focus_left,
            focus_right_label=self._focus_right,
        )
        self._calibration_overlay = CalibrationOverlayController(
            target_pattern=(9, 6),
            target_stride=5,
            fiducial_stride=5,
            fiducial_ids={"plate": 0, "rubber": 1},
        )

        self._left_view = RoiLabel(self._on_rect_update)
        self._right_view = RoiLabel(self._on_right_rect_update)
        self._left_view.setMinimumSize(320, 180)
        self._right_view.setMinimumSize(320, 180)
        self._left_view.setAlignment(QtCore.Qt.AlignCenter)
        self._right_view.setAlignment(QtCore.Qt.AlignCenter)
        self._left_view.setScaledContents(True)
        self._right_view.setScaledContents(True)
        self._right_view.setVisible(False)
        self._plate_map = PlateMapWidget()
        self._production_mode = False

        self._lane_button = QtWidgets.QPushButton("Edit Lane ROI")
        self._lane_right_button = QtWidgets.QPushButton("Edit Right Lane ROI")
        self._plate_button = QtWidgets.QPushButton("Edit Plate ROI")
        self._clear_lane_button = QtWidgets.QPushButton("Clear Lane ROI")
        self._clear_plate_button = QtWidgets.QPushButton("Clear Plate ROI")
        self._save_roi_button = QtWidgets.QPushButton("Save ROIs")
        self._load_roi_button = QtWidgets.QPushButton("Load ROIs")
        self._guide_button = QtWidgets.QPushButton("Calibration Guide")
        self._quick_cal_button = QtWidgets.QPushButton("Quick Calibrate")
        self._plate_cal_button = QtWidgets.QPushButton("Plate Plane Calibrate")

        self._mode_combo = QtWidgets.QComboBox()
        self._mode_combo.addItems([Mode.MODE_A.value, Mode.MODE_B.value])
        self._frame_diff = QtWidgets.QDoubleSpinBox()
        self._bg_diff = QtWidgets.QDoubleSpinBox()
        self._bg_alpha = QtWidgets.QDoubleSpinBox()
        self._edge_thresh = QtWidgets.QDoubleSpinBox()
        self._blob_thresh = QtWidgets.QDoubleSpinBox()
        self._min_area = QtWidgets.QSpinBox()
        self._min_circ = QtWidgets.QDoubleSpinBox()
        self._apply_detector = QtWidgets.QPushButton("Apply Detector")

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(self._record_button)
        controls.addWidget(self._stop_record_button)

        plate_column = QtWidgets.QVBoxLayout()
        plate_column.addWidget(self._plate_map)
        plate_column.addWidget(self._build_game_panel())
        plate_widget = QtWidgets.QWidget()
        plate_widget.setLayout(plate_column)
        self._plate_widget = plate_widget
        self._views_layout = QtWidgets.QHBoxLayout()
        self._views_layout.addWidget(self._left_view, 3)
        self._views_layout.addWidget(self._plate_widget, 2)
        self._views_layout.addWidget(self._right_view, 2)

        self._setup_group = QtWidgets.QGroupBox("Setup & Calibration")
        profile_row = QtWidgets.QHBoxLayout()
        profile_row.addWidget(self._profile_combo)
        profile_row.addWidget(self._profile_load)
        profile_row.addWidget(self._profile_name)
        profile_row.addWidget(self._profile_save)
        pitcher_row = QtWidgets.QHBoxLayout()
        pitcher_row.addWidget(self._pitcher_combo)
        pitcher_row.addWidget(self._pitcher_name_input)
        pitcher_row.addWidget(self._pitcher_add)
        device_row = QtWidgets.QHBoxLayout()
        device_row.addWidget(self._left_input)
        device_row.addWidget(self._right_input)
        roi_row = QtWidgets.QHBoxLayout()
        roi_row.addWidget(self._lane_button)
        roi_row.addWidget(self._lane_right_button)
        roi_row.addWidget(self._plate_button)
        roi_row.addWidget(self._clear_lane_button)
        roi_row.addWidget(self._clear_plate_button)
        roi_row.addWidget(self._save_roi_button)
        roi_row.addWidget(self._load_roi_button)
        calib_row = QtWidgets.QHBoxLayout()
        calib_row.addWidget(self._guide_button)
        calib_row.addWidget(self._quick_cal_button)
        calib_row.addWidget(self._plate_cal_button)
        action_row = QtWidgets.QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self._enter_button)
        setup_layout = QtWidgets.QVBoxLayout()
        setup_layout.addLayout(profile_row)
        setup_layout.addLayout(pitcher_row)
        setup_layout.addLayout(device_row)
        # Move ROI/calibration controls into menus to reduce clutter.
        setup_layout.addLayout(action_row)
        self._setup_group.setLayout(setup_layout)

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(self._setup_group)
        self._controls_widget = QtWidgets.QWidget()
        self._controls_widget.setLayout(controls)
        layout.addWidget(self._controls_widget)
        # Add error notification widget (Phase 2)
        self._error_notification = ErrorNotificationWidget(self)
        self._error_bridge = ErrorNotificationBridge(self._error_notification)
        layout.addWidget(self._error_notification)
        layout.addLayout(self._views_layout)
        self._health_panel = self._build_health_panel()
        layout.addWidget(self._health_panel)
        layout.addWidget(self._status_label)

        container = QtWidgets.QWidget()
        container.setObjectName("AppShell")
        container.setLayout(layout)
        self.setCentralWidget(container)
        self._build_menu()
        self._apply_modern_styles()

        self._start_button.clicked.connect(self._start_capture)
        self._stop_button.clicked.connect(self._stop_capture)
        self._restart_button.clicked.connect(self._restart_capture)
        self._record_button.clicked.connect(self._start_recording)
        self._stop_record_button.clicked.connect(self._stop_recording)
        self._training_button.clicked.connect(self._start_training_capture)
        self._refresh_button.clicked.connect(self._refresh_devices)
        self._replay_button.clicked.connect(self._start_replay)
        self._pause_button.clicked.connect(self._toggle_replay_pause)
        self._step_button.clicked.connect(self._step_replay)
        self._checklist_button.clicked.connect(self._open_checklist)
        self._record_settings_button.clicked.connect(self._open_record_settings)
        self._strike_settings_button.clicked.connect(self._open_strike_settings)
        self._detector_settings_button.clicked.connect(self._open_detector_settings)
        self._profile_load.clicked.connect(self._load_profile)
        self._profile_save.clicked.connect(self._save_profile)
        self._pitcher_add.clicked.connect(self._add_pitcher)
        self._pitcher_combo.currentTextChanged.connect(self._set_pitcher)
        self._low_perf_button.clicked.connect(self._apply_low_perf_mode)
        self._cue_card_button.clicked.connect(self._cue_card_test)
        self._enter_button.clicked.connect(self._enter_app)
        self._output_browse.clicked.connect(self._browse_output)
        self._manual_speed.valueChanged.connect(self._set_manual_speed)
        self._ball_combo.currentTextChanged.connect(self._set_ball_type)
        self._batter_height.valueChanged.connect(self._set_batter_height)
        self._top_ratio.valueChanged.connect(self._set_strike_ratios)
        self._bottom_ratio.valueChanged.connect(self._set_strike_ratios)
        self._save_strike_button.clicked.connect(self._save_strike_zone)
        self._lane_button.clicked.connect(lambda: self._set_roi_mode("lane"))
        self._lane_right_button.clicked.connect(lambda: self._set_roi_mode("lane_right"))
        self._plate_button.clicked.connect(lambda: self._set_roi_mode("plate"))
        self._clear_lane_button.clicked.connect(self._clear_lane)
        self._clear_plate_button.clicked.connect(self._clear_plate)
        self._save_roi_button.clicked.connect(self._save_rois)
        self._load_roi_button.clicked.connect(self._load_rois)
        self._guide_button.clicked.connect(self._open_calibration_guide)
        self._apply_detector.clicked.connect(self._apply_detector_config)
        self._quick_cal_button.clicked.connect(self._open_quick_calibrate)
        self._plate_cal_button.clicked.connect(self._open_plate_calibrate)

        self._refresh_devices()
        self._refresh_profiles()
        self._refresh_pitchers()
        self._load_rois()
        self._maybe_show_guide()
        self._load_detector_defaults()
        self._ball_combo.setCurrentText(self._config.ball.type)
        self._batter_height.setValue(self._config.strike_zone.batter_height_in)
        self._top_ratio.setValue(self._config.strike_zone.top_ratio)
        self._bottom_ratio.setValue(self._config.strike_zone.bottom_ratio)
        self._output_dir.setText(self._config.recording.output_dir)
        self._service.set_record_directory(Path(self._config.recording.output_dir))
        self._update_plate_map_zone()
        self._update_calib_summary()
        self._set_setup_mode(True)

        # Register cleanup tasks after all components are initialized (Phase 3)
        self._register_cleanup_tasks()

        # Initialize controllers (Phase: MainWindow refactoring)
        self._profile_manager = ProfileManager(
            profile_combo=self._profile_combo,
            profile_name_input=self._profile_name,
            pitcher_combo=self._pitcher_combo,
            pitcher_name_input=self._pitcher_name_input,
            left_input=self._left_input,
            right_input=self._right_input,
            status_label=self._status_label,
            roi_path=self._roi_path,
            on_profile_loaded=lambda name: self._enter_app(),
            on_rois_changed=lambda: self._load_rois(),
        )
        self._device_manager = DeviceManager(
            left_input=self._left_input,
            right_input=self._right_input,
            status_label=self._status_label,
            get_backend=lambda: self._service._backend,
        )
        self._calibration_manager = CalibrationManager(
            parent=self,
            config_path=self._config_path(),
            status_label=self._status_label,
            calib_summary=self._calib_summary,
            get_config=lambda: self._config,
            set_config=lambda config: setattr(self, "_config", config),
        )
        self._export_manager = ExportManager(
            parent=self,
            config_path=self._config_path(),
            roi_path=self._roi_path,
            get_config=lambda: self._config,
            get_session_dir=lambda: self._service.get_session_dir(),
            get_pitcher_name=lambda: self._profile_manager.pitcher_name,
            get_location_profile=lambda: self._profile_manager.location_profile,
        )
        self._roi_manager = RoiManager(
            roi_path=self._roi_path,
            lane_path=self._lane_path,
            left_view=self._left_view,
            right_view=self._right_view,
            status_label=self._status_label,
            get_camera_serials=lambda: (
                self._device_manager.get_left_serial(),
                self._device_manager.get_right_serial(),
            ),
        )
        self._replay_controller = ReplayController(
            parent=self,
            left_view=self._left_view,
            right_view=self._right_view,
            status_label=self._status_label,
            get_config=lambda: self._config,
            get_lane_rect=lambda: self._roi_manager.lane_rect,
            get_plate_rect=lambda: self._roi_manager.plate_rect,
            get_active_rect=lambda: self._roi_manager.active_rect,
            stop_capture=self._stop_capture,
            start_timer=lambda ms: self._timer.start(ms),
        )
        self._game_visualizer = GameVisualizer(
            plate_map=self._plate_map,
            status_label=self._game_status,
            score_label=self._game_score,
            streak_label=self._game_streak_label,
            get_config=lambda: self._config,
            get_pitch_paths=lambda: self._service.get_recent_pitch_paths(),
            build_strike_zone=build_strike_zone,
        )
        self._settings_manager = SettingsManager(
            parent=self,
            status_label=self._status_label,
            get_config=lambda: self._config,
            get_config_path=self._config_path,
            # Detector getters
            get_detector_mode=lambda: self._mode_combo.currentText(),
            get_frame_diff=lambda: self._frame_diff.value(),
            get_bg_diff=lambda: self._bg_diff.value(),
            get_bg_alpha=lambda: self._bg_alpha.value(),
            get_edge_thresh=lambda: self._edge_thresh.value(),
            get_blob_thresh=lambda: self._blob_thresh.value(),
            get_min_area=lambda: self._min_area.value(),
            get_min_circ=lambda: self._min_circ.value(),
            # Detector setters
            set_detector_mode=lambda v: self._mode_combo.setCurrentText(v),
            set_frame_diff=lambda v: self._frame_diff.setValue(v),
            set_bg_diff=lambda v: self._bg_diff.setValue(v),
            set_bg_alpha=lambda v: self._bg_alpha.setValue(v),
            set_edge_thresh=lambda v: self._edge_thresh.setValue(v),
            set_blob_thresh=lambda v: self._blob_thresh.setValue(v),
            set_min_area=lambda v: self._min_area.setValue(v),
            set_min_circ=lambda v: self._min_circ.setValue(v),
            # Strike zone getters
            get_ball_type=lambda: self._ball_combo.currentText(),
            get_batter_height=lambda: self._batter_height.value(),
            get_top_ratio=lambda: self._top_ratio.value(),
            get_bottom_ratio=lambda: self._bottom_ratio.value(),
            # Strike zone setters
            set_ball_type=lambda v: self._ball_combo.setCurrentText(v),
            set_batter_height=lambda v: self._batter_height.setValue(v),
            set_top_ratio=lambda v: self._top_ratio.setValue(v),
            set_bottom_ratio=lambda v: self._bottom_ratio.setValue(v),
            # Service callbacks
            apply_detector_to_service=self._apply_detector_to_service,
            apply_ball_type_to_service=lambda v: self._service.set_ball_type(v),
            apply_batter_height_to_service=lambda v: self._service.set_batter_height_in(v),
            apply_strike_ratios_to_service=lambda t, b: self._service.set_strike_zone_ratios(t, b),
            update_plate_map_zone=self._update_plate_map_zone,
        )
        self._capture_controller = CaptureController(
            parent=self,
            status_label=self._status_label,
            get_config=lambda: self._config,
            get_config_path=self._config_path,
            get_left_serial=lambda: self._device_manager.get_left_serial(),
            get_right_serial=lambda: self._device_manager.get_right_serial(),
            get_roi_path=lambda: self._roi_path,
            get_lane_path=lambda: self._lane_path,
            start_timer=lambda ms: self._timer.start(ms),
            stop_timer=lambda: self._timer.stop(),
            stop_replay=self._stop_replay,
            start_capture_service=lambda cfg, left, right, path: self._service.start_capture(cfg, left, right, config_path=path),
            stop_capture_service=lambda: self._service.stop_capture(),
        )
        self._recording_controller = RecordingController(
            parent=self,
            status_label=self._status_label,
            get_config=lambda: self._config,
            get_config_path=self._config_path,
            get_session_name=lambda: self._session_name.text(),
            set_session_name=lambda v: self._session_name.setText(v),
            get_output_dir=lambda: self._output_dir.text(),
            set_output_dir_widget=lambda v: self._output_dir.setText(v),
            get_roi_path=lambda: self._roi_path,
            get_pitcher_name=lambda: self._profile_manager.pitcher_name,
            get_location_profile=lambda: self._profile_manager.location_profile,
            health_check=self._health_ok,
            start_recording_service=lambda name, mode: self._service.start_recording(session_name=name, mode=mode),
            stop_recording_service=lambda: self._service.stop_recording(),
            set_record_directory=lambda p: self._service.set_record_directory(p),
            set_manual_speed_mph=lambda s: self._service.set_manual_speed_mph(s),
            get_session_summary=lambda: self._service.get_session_summary(),
            get_session_dir=lambda: self._service.get_session_dir(),
        )

        self._run_startup_dialog()

    def _apply_modern_styles(self) -> None:
        """Apply the centralized design system to the main app shell."""
        sm = get_style_manager()

        for button in (
            self._start_button,
            self._restart_button,
            self._replay_button,
            self._enter_button,
            self._profile_load,
            self._apply_detector,
        ):
            sm.style_button(button, "primary")

        for button in (
            self._record_button,
            self._training_button,
            self._profile_save,
            self._pitcher_add,
            self._save_strike_button,
            self._save_roi_button,
        ):
            sm.style_button(button, "success")

        for button in (
            self._stop_button,
            self._stop_record_button,
        ):
            sm.style_button(button, "danger")

        for button in (
            self._refresh_button,
            self._pause_button,
            self._step_button,
            self._record_settings_button,
            self._strike_settings_button,
            self._detector_settings_button,
            self._low_perf_button,
            self._cue_card_button,
            self._checklist_button,
            self._output_browse,
            self._lane_button,
            self._lane_right_button,
            self._plate_button,
            self._clear_lane_button,
            self._clear_plate_button,
            self._load_roi_button,
            self._guide_button,
            self._quick_cal_button,
            self._plate_cal_button,
        ):
            sm.style_button(button, "default")

        for widget in (
            self._left_input,
            self._right_input,
            self._session_name,
            self._profile_combo,
            self._profile_name,
            self._pitcher_combo,
            self._pitcher_name_input,
            self._output_dir,
            self._manual_speed,
            self._ball_combo,
            self._batter_height,
            self._top_ratio,
            self._bottom_ratio,
            self._mode_combo,
            self._frame_diff,
            self._bg_diff,
            self._bg_alpha,
            self._edge_thresh,
            self._blob_thresh,
            self._min_area,
            self._min_circ,
        ):
            sm.style_input(widget)

        self._controls_widget.setProperty("surface", "toolbar")
        sm.polish(self._controls_widget)
        self._plate_widget.setProperty("surface", "card")
        sm.polish(self._plate_widget)
        self._left_view.setProperty("surface", "preview")
        self._right_view.setProperty("surface", "preview")
        sm.polish(self._left_view)
        sm.polish(self._right_view)
        sm.style_status_indicator(self._status_label, "info")

    def _start_capture(self) -> None:
        self._capture_controller.start_capture()

    def _stop_capture(self) -> None:
        self._capture_controller.stop_capture()

    def _restart_capture(self) -> None:
        self._capture_controller.restart_capture()

    def _start_recording(self) -> None:
        self._recording_controller.start_recording()

    def _browse_output(self) -> None:
        self._recording_controller.browse_output()

    def _set_output_dir(self, path: str) -> None:
        self._recording_controller.set_output_dir(path)

    def _set_manual_speed(self, value: float) -> None:
        self._recording_controller.set_manual_speed(value)

    def _stop_recording(self) -> None:
        self._recording_controller.stop_recording()

    def _set_setup_mode(self, active: bool) -> None:
        for widget in (
            self._start_button,
            self._stop_button,
            self._restart_button,
            self._record_button,
            self._stop_record_button,
            self._training_button,
            self._replay_button,
            self._pause_button,
            self._step_button,
            self._record_settings_button,
            self._strike_settings_button,
            self._detector_settings_button,
            self._checklist_button,
        ):
            widget.setEnabled(not active)
        self._setup_group.setVisible(active)

    def _enter_app(self) -> None:
        self._set_setup_mode(False)
        # Note: Pitcher state now saved by ProfileManager.set_pitcher()

    def _refresh_profiles(self) -> None:
        self._profile_manager.refresh_profiles()

    def _refresh_pitchers(self) -> None:
        self._profile_manager.refresh_pitchers()

    def _load_profile(self) -> None:
        self._profile_manager.load_profile(self)

    def _save_profile(self) -> None:
        self._profile_manager.save_profile(self)

    def _add_pitcher(self) -> None:
        self._profile_manager.add_pitcher()

    def _set_pitcher(self, name: str) -> None:
        self._profile_manager.set_pitcher(name)

    def _run_startup_dialog(self) -> None:
        dialog = StartupDialog(self)
        result = dialog.exec()
        if result != QtWidgets.QDialog.Accepted:
            return
        profile_name, pitcher = dialog.values()
        self._profile_manager.apply_startup_selection(profile_name, pitcher)
        if profile_name:
            self._load_profile()
        self._calibration_manager.run_calibration_wizard()

    def _run_calibration_wizard(self) -> None:
        self._calibration_manager.run_calibration_wizard()

    def _cue_card_test(self) -> None:
        try:
            detections = self._service.get_latest_detections()
        except Exception:
            show_message_dialog(
                self,
                "Cue Card Test",
                "Start capture to run the cue card test.",
                tone="info",
            )
            return
        total = sum(len(items) for items in detections.values())
        show_message_dialog(
            self,
            "Cue Card Test",
            f"Detections in current frame: {total}\n"
            "Hold the cue card in the lane and confirm detections appear.",
            tone="info",
        )

    def _apply_low_perf_mode(self) -> None:
        if self._timer.isActive():
            show_message_dialog(
                self,
                "Low Perf Mode",
                "Stop capture before applying low performance settings.",
                tone="info",
            )
            return
        config_path = self._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("camera", {})
        data.setdefault("ui", {})
        data["camera"]["width"] = 1280
        data["camera"]["height"] = 720
        data["camera"]["fps"] = 30
        data["ui"]["refresh_hz"] = 10
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))
        self._config = load_config(config_path)
        self._load_detector_defaults()
        self._status_label.setText("Low performance mode applied.")

    def _default_session_name(self) -> Optional[str]:
        return self._recording_controller.default_session_name()

    def _upload_session(self, summary) -> None:
        self._export_manager.upload_session(summary)

    def _save_session_export(
        self,
        summary,
        session_dir: Optional[Path],
        export_type: Optional[str],
    ) -> None:
        self._export_manager.save_export(summary, export_type)

    def _start_training_capture(self) -> None:
        self._recording_controller.start_training_capture()

    def _update_preview(self) -> None:
        if self._replay_controller.is_active:
            self._update_replay()
            return

        # Get frames from service
        try:
            left_frame, right_frame = self._service.get_preview_frames()
        except RuntimeError as exc:
            self._status_label.setText(str(exc))
            return

        self._left_view.set_image_size(left_frame.width, left_frame.height)

        # Get ROI overlays
        lane_rect = self._roi_manager.lane_rect
        plate_rect = self._roi_manager.plate_rect
        active_rect = self._roi_manager.active_rect
        overlays_left = roi_overlays(lane_rect, plate_rect, active_rect)
        lane_right = self._roi_manager.lane_rect_right or lane_rect
        overlays_right = roi_overlays(lane_right, plate_rect, active_rect)

        # Get detections
        detections = self._service.get_latest_detections()
        gated = self._service.get_latest_gated_detections()
        left_dets = detections.get(left_frame.camera_id, [])
        right_dets = detections.get(right_frame.camera_id, [])
        left_gated = gated.get(left_frame.camera_id, {})
        right_gated = gated.get(right_frame.camera_id, {})

        # Get strike zone result
        strike = self._service.get_strike_result()
        zone = None
        if strike.zone_row is not None and strike.zone_col is not None:
            zone = (strike.zone_row, strike.zone_col)

        # Process calibration overlays (checkerboard and fiducials)
        checkerboard, fiducials = self._calibration_overlay.process_frame(left_frame.image)

        # Compute focus scores and get overlay values
        focus_left, focus_right = self._focus_monitor.compute_scores(
            left_frame.image, right_frame.image
        )
        focus_overlay_left, focus_overlay_right = self._focus_monitor.get_overlay_scores(
            self._calibration_overlay.show_target
        )

        # Render left view
        self._left_view.setPixmap(
            frame_to_pixmap(
                left_frame.image,
                overlays_left,
                left_dets,
                left_gated.get("lane", []),
                left_gated.get("plate", []),
                plate_rect=plate_rect,
                zone=zone,
                checkerboard=checkerboard,
                fiducials=fiducials,
                focus_score=focus_overlay_left,
            )
        )

        # Render right view if visible
        if self._right_view.isVisible():
            self._right_view.setPixmap(
                frame_to_pixmap(
                    right_frame.image,
                    overlays_right,
                    right_dets,
                    right_gated.get("lane", []),
                    right_gated.get("plate", []),
                    plate_rect=plate_rect,
                    zone=zone,
                    focus_score=focus_overlay_right,
                )
            )

        # Update plate map
        self._update_plate_map()

        # Update health stats
        stats = self._service.get_stats()
        plate_metrics = self._service.get_plate_metrics()
        if stats:
            left_stats = stats.get("left", {})
            right_stats = stats.get("right", {})

            # Update health labels
            self._health_left.setText(
                "L: fps={:.1f} jitter={:.1f}ms drops={}".format(
                    left_stats.get("fps_avg", 0.0),
                    left_stats.get("jitter_p95_ms", 0.0),
                    int(left_stats.get("dropped_frames", 0)),
                )
            )
            self._health_right.setText(
                "R: fps={:.1f} jitter={:.1f}ms drops={}".format(
                    right_stats.get("fps_avg", 0.0),
                    right_stats.get("jitter_p95_ms", 0.0),
                    int(right_stats.get("dropped_frames", 0)),
                )
            )

            # Update focus display via controller
            self._focus_monitor.update_display(focus_left, focus_right)

            # Update status label
            zone_label = "-"
            if strike.zone_row is not None and strike.zone_col is not None:
                zone_label = f"{strike.zone_row},{strike.zone_col}"
            self._status_label.setText(
                "fps L={:.1f} R={:.1f} drops L={} R={} run={:.2f} rise={:.2f} strike={} zone={}".format(
                    left_stats.get("fps_avg", 0.0),
                    right_stats.get("fps_avg", 0.0),
                    int(left_stats.get("dropped_frames", 0)),
                    int(right_stats.get("dropped_frames", 0)),
                    plate_metrics.run_in,
                    plate_metrics.rise_in,
                    "Y" if strike.is_strike else "N",
                    zone_label,
                )
            )

    def _start_replay(self) -> None:
        self._replay_controller.start_replay()

    def _stop_replay(self) -> None:
        self._replay_controller.stop_replay()

    def _update_replay(self) -> None:
        self._replay_controller.update_replay()

    def _toggle_replay_pause(self) -> None:
        self._replay_controller.toggle_pause()

    def _step_replay(self) -> None:
        self._replay_controller.step_frame()

    def _refresh_devices(self) -> None:
        self._device_manager.refresh_devices()

    def _set_roi_mode(self, mode: str) -> None:
        self._roi_manager.set_roi_mode(mode)

    def _on_rect_update(self, rect: Rect, final: bool) -> None:
        self._roi_manager.on_rect_update(rect, final)

    def _on_right_rect_update(self, rect: Rect, final: bool) -> None:
        self._roi_manager.on_right_rect_update(rect, final)

    def _clear_lane(self) -> None:
        self._roi_manager.clear_lane()

    def _clear_plate(self) -> None:
        self._roi_manager.clear_plate()

    def _reset_focus_peaks(self) -> None:
        """Reset focus quality peak tracking."""
        self._focus_monitor.reset_peaks()
        self._status_label.setText("Focus peak values reset. Adjust lenses and watch for green.")

    def _save_rois(self) -> None:
        self._roi_manager.save_rois()

    def _load_rois(self) -> None:
        self._roi_manager.load_rois()

    def _load_detector_defaults(self) -> None:
        self._settings_manager.load_detector_defaults()

    def _apply_detector_config(self) -> None:
        self._settings_manager.apply_detector_config()

    def _apply_detector_to_service(
        self, detector_cfg: CvDetectorConfig, mode: Mode, ml_settings: dict
    ) -> None:
        """Apply detector config to service (helper for SettingsManager)."""
        self._service.set_detector_config(
            detector_cfg,
            mode,
            detector_type=ml_settings["detector_type"],
            model_path=ml_settings["model_path"],
            model_input_size=ml_settings["model_input_size"],
            model_conf_threshold=ml_settings["model_conf_threshold"],
            model_class_id=ml_settings["model_class_id"],
            model_format=ml_settings["model_format"],
        )
        self._service.set_detection_threading(
            ml_settings["threading_mode"], ml_settings["worker_count"]
        )

    def _set_ball_type(self, ball_type: str) -> None:
        self._settings_manager.set_ball_type(ball_type)

    def _set_batter_height(self, value: float) -> None:
        self._settings_manager.set_batter_height(value)

    def _set_strike_ratios(self) -> None:
        self._settings_manager.set_strike_ratios()

    def _save_strike_zone(self) -> None:
        self._settings_manager.save_strike_zone()

    def _health_ok(self) -> bool:
        stats = self._service.get_stats()
        if not stats:
            return False
        left = stats.get("left", {})
        right = stats.get("right", {})
        fps_ok = left.get("fps_avg", 0.0) >= 58.0 and right.get("fps_avg", 0.0) >= 58.0
        drops_ok = (
            int(left.get("dropped_frames", 0)) <= 2
            and int(right.get("dropped_frames", 0)) <= 2
        )
        return fps_ok and drops_ok

    def _update_plate_map_zone(self) -> None:
        self._game_visualizer.update_plate_map_zone()

    def _update_plate_map(self) -> None:
        summary = self._service.get_session_summary()
        self._game_visualizer.update_plate_map(summary)

    def _reset_tic_tac_toe_game(self) -> None:
        self._game_visualizer.reset_game()

    def _set_production_mode(self, enabled: bool) -> None:
        self._production_mode = enabled
        self._setup_group.setVisible(not enabled)
        if enabled:
            self._health_panel.setVisible(False)
            self._status_label.setVisible(False)
            self._controls_widget.setVisible(False)
            self._right_view.setVisible(False)
            self._right_camera_action.setChecked(False)
            self._views_layout.setStretch(0, 3)
            self._views_layout.setStretch(1, 4)
            self._views_layout.setStretch(2, 0)
        else:
            self._health_panel.setVisible(self._health_toggle_action.isChecked())
            self._status_label.setVisible(True)
            self._controls_widget.setVisible(True)
            self._right_view.setVisible(self._right_camera_action.isChecked())
            self._views_layout.setStretch(0, 3)
            self._views_layout.setStretch(1, 2)
            self._views_layout.setStretch(2, 2)
        if enabled:
            self._status_label.setText("Production mode.")

    def _set_target_mode(self, enabled: bool) -> None:
        self._game_visualizer.set_target_mode(enabled)

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        capture_menu = menu_bar.addMenu("Capture")
        start_action = capture_menu.addAction("Start Capture")
        start_action.setShortcut(QtGui.QKeySequence("F5"))
        stop_action = capture_menu.addAction("Stop Capture")
        stop_action.setShortcut(QtGui.QKeySequence("F6"))
        restart_action = capture_menu.addAction("Restart Capture")
        restart_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+R"))
        capture_menu.addSeparator()
        record_action = capture_menu.addAction("Start Recording")
        record_action.setShortcut(QtGui.QKeySequence("Ctrl+R"))
        stop_record_action = capture_menu.addAction("Stop Recording")
        stop_record_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        capture_menu.addSeparator()
        training_action = capture_menu.addAction("Training Capture")
        training_action.setShortcut(QtGui.QKeySequence("Ctrl+T"))
        start_action.triggered.connect(self._start_capture)
        stop_action.triggered.connect(self._stop_capture)
        restart_action.triggered.connect(self._restart_capture)
        record_action.triggered.connect(self._start_recording)
        stop_record_action.triggered.connect(self._stop_recording)
        training_action.triggered.connect(self._start_training_capture)

        calibration_menu = menu_bar.addMenu("Calibration")
        guide_action = calibration_menu.addAction("Calibration Guide")
        guide_action.setShortcut(QtGui.QKeySequence("Ctrl+G"))
        wizard_action = calibration_menu.addAction("Calibration Wizard")
        wizard_action.setShortcut(QtGui.QKeySequence("Ctrl+W"))
        quick_action = calibration_menu.addAction("Quick Calibrate")
        quick_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        plate_action = calibration_menu.addAction("Plate Plane Calibrate")
        plate_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+P"))
        guide_action.triggered.connect(self._open_calibration_guide)
        wizard_action.triggered.connect(self._run_calibration_wizard)
        quick_action.triggered.connect(self._open_quick_calibrate)
        plate_action.triggered.connect(self._open_plate_calibrate)

        roi_menu = menu_bar.addMenu("ROI")
        lane_action = roi_menu.addAction("Edit Lane ROI")
        lane_action.setShortcut(QtGui.QKeySequence("Ctrl+1"))
        lane_right_action = roi_menu.addAction("Edit Right Lane ROI")
        lane_right_action.setShortcut(QtGui.QKeySequence("Ctrl+2"))
        plate_roi_action = roi_menu.addAction("Edit Plate ROI")
        plate_roi_action.setShortcut(QtGui.QKeySequence("Ctrl+3"))
        roi_menu.addSeparator()
        clear_lane_action = roi_menu.addAction("Clear Lane ROI")
        clear_plate_action = roi_menu.addAction("Clear Plate ROI")
        roi_menu.addSeparator()
        save_roi_action = roi_menu.addAction("Save ROIs")
        save_roi_action.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        load_roi_action = roi_menu.addAction("Load ROIs")
        load_roi_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        lane_action.triggered.connect(lambda: self._set_roi_mode("lane"))
        lane_right_action.triggered.connect(lambda: self._set_roi_mode("lane_right"))
        plate_roi_action.triggered.connect(lambda: self._set_roi_mode("plate"))
        clear_lane_action.triggered.connect(self._clear_lane)
        clear_plate_action.triggered.connect(self._clear_plate)
        save_roi_action.triggered.connect(self._save_rois)
        load_roi_action.triggered.connect(self._load_rois)

        settings_menu = menu_bar.addMenu("Settings")
        record_settings_action = settings_menu.addAction("Recording Settings")
        record_settings_action.setShortcut(QtGui.QKeySequence("Ctrl+,"))
        strike_settings_action = settings_menu.addAction("Strike Zone Settings")
        strike_settings_action.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        detector_settings_action = settings_menu.addAction("Detector Settings")
        detector_settings_action.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        record_settings_action.triggered.connect(self._open_record_settings)
        strike_settings_action.triggered.connect(self._open_strike_settings)
        detector_settings_action.triggered.connect(self._open_detector_settings)

        tools_menu = menu_bar.addMenu("Tools")
        refresh_action = tools_menu.addAction("Refresh Devices")
        refresh_action.setShortcut(QtGui.QKeySequence("F5"))
        checklist_action = tools_menu.addAction("Checklist")
        checklist_action.setShortcut(QtGui.QKeySequence("Ctrl+L"))
        low_perf_action = tools_menu.addAction("Low Perf Mode")
        low_perf_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+L"))
        cue_card_action = tools_menu.addAction("Cue Card Test")
        reset_game_action = tools_menu.addAction("Reset Game")
        reset_game_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+G"))
        target_mode_action = tools_menu.addAction("Target Mode")
        target_mode_action.setCheckable(True)
        target_mode_action.setChecked(False)
        target_mode_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+T"))
        refresh_action.triggered.connect(self._refresh_devices)
        checklist_action.triggered.connect(self._open_checklist)
        low_perf_action.triggered.connect(self._apply_low_perf_mode)
        cue_card_action.triggered.connect(self._cue_card_test)
        reset_game_action.triggered.connect(self._reset_tic_tac_toe_game)
        target_mode_action.toggled.connect(self._set_target_mode)

        review_menu = menu_bar.addMenu("Review")
        replay_action = review_menu.addAction("Replay")
        replay_action.setShortcut(QtGui.QKeySequence("Ctrl+P"))
        pause_action = review_menu.addAction("Pause/Resume Replay")
        pause_action.setShortcut(QtGui.QKeySequence("Space"))
        step_action = review_menu.addAction("Step Replay")
        step_action.setShortcut(QtGui.QKeySequence("Right"))
        replay_action.triggered.connect(self._start_replay)
        pause_action.triggered.connect(self._toggle_replay_pause)
        step_action.triggered.connect(self._step_replay)

        view_menu = menu_bar.addMenu("View")
        self._health_toggle_action = QtGui.QAction("Show Health Panel", self)
        self._health_toggle_action.setCheckable(True)
        self._health_toggle_action.setChecked(True)
        self._health_toggle_action.setShortcut(QtGui.QKeySequence("F2"))
        self._health_toggle_action.toggled.connect(self._health_panel.setVisible)
        view_menu.addAction(self._health_toggle_action)
        self._right_camera_action = QtGui.QAction("Show Right Camera", self)
        self._right_camera_action.setCheckable(True)
        self._right_camera_action.setChecked(False)
        self._right_camera_action.setShortcut(QtGui.QKeySequence("F3"))
        self._right_camera_action.toggled.connect(self._right_view.setVisible)
        view_menu.addAction(self._right_camera_action)
        self._production_action = QtGui.QAction("Production Mode", self)
        self._production_action.setCheckable(True)
        self._production_action.setChecked(False)
        self._production_action.setShortcut(QtGui.QKeySequence("F11"))
        self._production_action.toggled.connect(self._set_production_mode)
        view_menu.addAction(self._production_action)

        help_menu = menu_bar.addMenu("Help")
        shortcuts_action = help_menu.addAction("Keyboard Shortcuts")
        shortcuts_action.setShortcut(QtGui.QKeySequence("F1"))
        about_action = help_menu.addAction("About")
        shortcuts_action.triggered.connect(self._show_keyboard_shortcuts)
        about_action.triggered.connect(self._show_about)

    def _build_health_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Health")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._health_left)
        layout.addWidget(self._health_right)
        layout.addWidget(self._focus_left)
        layout.addWidget(self._focus_right)

        # Add button to reset focus peak tracking
        reset_focus_btn = GlassButton("Reset Focus Peaks", variant="ghost")
        reset_focus_btn.clicked.connect(self._reset_focus_peaks)
        layout.addWidget(reset_focus_btn)

        layout.addWidget(self._calib_summary)
        panel.setLayout(layout)
        return panel

    def _build_game_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Game")
        layout = QtWidgets.QVBoxLayout()
        sm = get_style_manager()
        self._game_status = QtWidgets.QLabel("Ready.")
        sm.style_label(self._game_status, "status")
        self._game_score = QtWidgets.QLabel("Score X:0  O:0  R:0")
        sm.style_label(self._game_score, "status")
        self._game_streak_label = QtWidgets.QLabel("Streak: 0")
        sm.style_label(self._game_streak_label, "status")
        reset = GlassButton("Reset Game", variant="ghost")
        reset.clicked.connect(self._reset_tic_tac_toe_game)
        layout.addWidget(self._game_status)
        layout.addWidget(self._game_score)
        layout.addWidget(self._game_streak_label)
        layout.addWidget(reset)
        panel.setLayout(layout)
        return panel

    def _build_detector_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Detector (Quick)")
        form = QtWidgets.QFormLayout()
        for field in (
            self._frame_diff,
            self._bg_diff,
            self._bg_alpha,
            self._edge_thresh,
            self._blob_thresh,
            self._min_circ,
        ):
            field.setDecimals(2)
            field.setMaximum(10_000.0)
        self._bg_alpha.setMaximum(1.0)
        self._bg_alpha.setSingleStep(0.01)
        self._min_area.setMaximum(100_000)
        form.addRow("Mode", self._mode_combo)
        form.addRow("Frame diff", self._frame_diff)
        form.addRow("BG diff", self._bg_diff)
        form.addRow("BG alpha", self._bg_alpha)
        form.addRow("Edge thresh", self._edge_thresh)
        form.addRow("Blob thresh", self._blob_thresh)
        form.addRow("Min area", self._min_area)
        form.addRow("Min circularity", self._min_circ)
        form.addRow(self._apply_detector)
        panel.setLayout(form)
        return panel

    def _open_calibration_guide(self) -> None:
        self._calibration_manager.open_calibration_guide()

    def _open_quick_calibrate(self) -> None:
        self._calibration_manager.open_quick_calibrate()

    def _open_plate_calibrate(self) -> None:
        self._calibration_manager.open_plate_calibrate()

    def _update_calib_summary(self) -> None:
        self._calibration_manager.update_calib_summary()

    def _open_checklist(self) -> None:
        dialog = ChecklistDialog(self)
        dialog.exec()

    def _open_record_settings(self) -> None:
        dialog = RecordingSettingsDialog(
            self,
            session=self._session_name.text(),
            output_dir=self._output_dir.text(),
            speed_mph=self._manual_speed.value(),
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            session, output_dir, speed = dialog.values()
            self._session_name.setText(session)
            self._set_output_dir(output_dir)
            self._manual_speed.setValue(speed)
            self._set_manual_speed(speed)

    def _open_strike_settings(self) -> None:
        values = self._settings_manager.get_strike_dialog_values()
        dialog = StrikeZoneSettingsDialog(
            self,
            ball_type=values["ball_type"],
            batter_height=values["batter_height"],
            top_ratio=values["top_ratio"],
            bottom_ratio=values["bottom_ratio"],
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            ball_type, height, top_ratio, bottom_ratio = dialog.values()
            self._settings_manager.update_strike_settings(
                ball_type, height, top_ratio, bottom_ratio
            )
            self._save_strike_zone()

    def _open_detector_settings(self) -> None:
        values = self._settings_manager.get_detector_dialog_values()
        dialog = DetectorSettingsDialog(
            self,
            mode=values["mode"],
            frame_diff=values["frame_diff"],
            bg_diff=values["bg_diff"],
            bg_alpha=values["bg_alpha"],
            edge_thresh=values["edge_thresh"],
            blob_thresh=values["blob_thresh"],
            min_area=values["min_area"],
            min_circ=values["min_circ"],
            threading_mode=values["threading_mode"],
            worker_count=values["worker_count"],
            detector_type=values["detector_type"],
            model_path=values["model_path"],
            model_input_size=values["model_input_size"],
            model_conf_threshold=values["model_conf_threshold"],
            model_class_id=values["model_class_id"],
            model_format=values["model_format"],
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            values = dialog.values()
            self._settings_manager.update_detector_settings(values)
            self._apply_detector_config()

    def _show_keyboard_shortcuts(self) -> None:
        """Open keyboard shortcuts documentation."""
        shortcuts_path = Path("docs/KEYBOARD_SHORTCUTS.md")
        if not shortcuts_path.exists():
            show_message_dialog(
                self,
                "Keyboard Shortcuts",
                "Keyboard shortcuts documentation not found.\n\n"
                "Expected location: docs/KEYBOARD_SHORTCUTS.md",
                tone="info",
            )
            return

        # Open the file with the system default application
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                os.startfile(shortcuts_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", shortcuts_path], check=True)
            else:
                subprocess.run(["xdg-open", shortcuts_path], check=True)
        except Exception as exc:
            show_message_dialog(
                self,
                "Keyboard Shortcuts",
                f"Failed to open shortcuts documentation: {exc}\n\n"
                f"File location: {shortcuts_path.absolute()}",
                tone="warning",
            )

    def _show_about(self) -> None:
        """Show About dialog with version information."""
        git_commit = self._get_git_commit()
        version_text = f"PitchTracker v{APP_VERSION}"
        if git_commit:
            version_text += f"\nCommit: {git_commit}"

        about_text = (
            f"{version_text}\n"
            f"Schema: {SCHEMA_VERSION}\n\n"
            f"A high-speed stereo vision system for baseball/softball pitch tracking.\n\n"
            f"Features:\n"
            f"  • 60 FPS stereo video capture\n"
            f"  • Real-time ball detection and tracking\n"
            f"  • Physics-based trajectory fitting\n"
            f"  • Strike zone analysis\n"
            f"  • Session recording and replay\n\n"
            f"Documentation: docs/\n"
            f"Issues: github.com/berginj/PitchTracker/issues"
        )

        show_message_dialog(self, "About PitchTracker", about_text, tone="info")

    def _set_target_overlay(self, enabled: bool) -> None:
        self._calibration_overlay.set_target_overlay(enabled)

    def _set_fiducial_overlay(self, enabled: bool) -> None:
        self._calibration_overlay.set_fiducial_overlay(enabled)

    def _propose_right_lane(self) -> None:
        lane_rect = self._roi_manager.lane_rect
        if lane_rect is None:
            show_message_dialog(
                self,
                "Propose Right Lane",
                "Draw the left lane ROI first.",
                tone="info",
            )
            return
        with self._latest_lock:
            left_frame = self._left_latest
            right_frame = self._right_latest
        if left_frame is None or right_frame is None:
            show_message_dialog(
                self,
                "Propose Right Lane",
                "Start capture before proposing the right lane.",
                tone="warning",
            )
            return
        left_w, left_h = left_frame.width, left_frame.height
        right_w, right_h = right_frame.width, right_frame.height
        x1, y1, x2, y2 = lane_rect
        nx1 = x1 / max(left_w, 1)
        ny1 = y1 / max(left_h, 1)
        nx2 = x2 / max(left_w, 1)
        ny2 = y2 / max(left_h, 1)
        rx1 = int(nx1 * right_w)
        ry1 = int(ny1 * right_h)
        rx2 = int(nx2 * right_w)
        ry2 = int(ny2 * right_h)
        shift = 0.0
        try:
            detections = self._service.get_latest_detections()
            left_id = self._device_manager.get_left_serial()
            right_id = self._device_manager.get_right_serial()
            left_dets = detections.get(left_id, [])
            right_dets = detections.get(right_id, [])
            if left_dets and right_dets:
                left_mean = sum(det.u for det in left_dets) / len(left_dets)
                right_mean = sum(det.u for det in right_dets) / len(right_dets)
                shift = right_mean - left_mean
        except Exception:
            shift = 0.0
        rx1 = int(rx1 + shift)
        rx2 = int(rx2 + shift)
        rx1 = max(0, min(rx1, right_w - 1))
        rx2 = max(0, min(rx2, right_w - 1))
        self._roi_manager.lane_rect_right = (rx1, ry1, rx2, ry2)
        self._status_label.setText("Proposed right lane ROI.")

    def _maybe_show_guide(self) -> None:
        marker = Path("configs/.first_run_done")
        if marker.exists():
            return
        QtCore.QTimer.singleShot(300, self._open_calibration_guide)
        try:
            marker.write_text("ok")
        except OSError:
            pass

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash (short form).

        Returns:
            Short commit hash (7 chars) or None if not in git repo
        """
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _config_path(self) -> Path:
        return self._config_path_value

    # ========================================================================
    # System Hardening Methods (Phase 2-4)
    # ========================================================================

    def _validate_config_at_startup(self, config_path: Path) -> None:
        """Validate configuration at startup (Phase 4).

        Args:
            config_path: Path to configuration file
        """
        try:
            config = load_config(config_path)
            validator = ConfigValidator()
            is_valid, issues = validator.validate(config)

            # Show errors (blocking)
            errors = [i for i in issues if i.severity == "error"]
            if errors:
                error_text = "\n".join([f"• {e.field}: {e.message}" for e in errors])
                show_message_dialog(
                    None,
                    "Configuration Error",
                    f"Configuration validation failed:\n\n{error_text}\n\n"
                    f"Please fix these errors in {config_path}",
                    tone="error",
                )
                import sys
                sys.exit(1)

            # Show warnings (non-blocking)
            warnings = [i for i in issues if i.severity == "warning"]
            if warnings:
                warning_text = "\n".join([f"• {w.field}: {w.message}" for w in warnings])
                show_message_dialog(
                    None,
                    "Configuration Warnings",
                    f"Configuration has warnings:\n\n{warning_text}\n\n"
                    f"The application will continue, but you may want to review these.",
                    tone="warning",
                )

        except Exception as exc:
            show_message_dialog(
                None,
                "Configuration Error",
                f"Failed to validate configuration:\n\n{exc}",
                tone="error",
            )
            import sys
            sys.exit(1)

    def _init_error_handling(self) -> None:
        """Initialize error handling system (Phase 2)."""
        # Get global error bus (auto-created)
        self._error_bus = get_error_bus()

        # Setup error recovery
        self._recovery_manager = get_recovery_manager()

        # Register custom recovery handlers
        self._recovery_manager.register_handler("stop_session", lambda event: self._stop_recording())
        self._recovery_manager.register_handler("shutdown", lambda event: self.close())

        # Start recovery manager
        self._recovery_manager.start()

        logger.info("Error handling system initialized")

    def _init_resource_monitoring(self) -> None:
        """Start resource monitoring (Phase 3)."""
        self._resource_monitor = get_resource_monitor()

        # Start monitoring thread
        self._resource_monitor.start()

        logger.info("Resource monitoring started")

    def _init_resource_limits(self) -> None:
        """Configure resource limits (Phase 3)."""
        limits = ResourceLimits(
            # Memory limits (MB)
            max_memory_mb=6000.0,  # 6GB for high-end systems
            warning_memory_mb=3000.0,  # 3GB warning

            # CPU limits (%)
            max_cpu_percent=90.0,
            warning_cpu_percent=75.0,

            # Disk space (GB)
            critical_disk_gb=10.0,
            warning_disk_gb=30.0,
            recommended_disk_gb=100.0,

            # Queue sizes
            detection_queue_size=10,
            recording_queue_size=30,

            # Timeouts (seconds)
            camera_open_timeout=15.0,
            shutdown_timeout=60.0,
        )

        # Validate and set
        set_resource_limits(limits)

        logger.info("Resource limits configured")

    def _register_cleanup_tasks(self) -> None:
        """Register cleanup tasks for graceful shutdown (Phase 3)."""
        self._cleanup_manager = get_cleanup_manager()

        # Critical tasks (must succeed)
        self._cleanup_manager.register_cleanup(
            "stop_capture",
            self._service.stop_capture,
            timeout=10.0,
            critical=True
        )

        self._cleanup_manager.register_cleanup(
            "stop_recording",
            lambda: self._service.stop_recording() if hasattr(self, "_service") else None,
            timeout=10.0,
            critical=True
        )

        # Non-critical tasks (nice to have)
        self._cleanup_manager.register_cleanup(
            "stop_monitoring",
            lambda: self._resource_monitor.stop(),
            timeout=2.0,
            critical=False
        )

        self._cleanup_manager.register_cleanup(
            "stop_recovery",
            lambda: self._recovery_manager.stop(),
            timeout=2.0,
            critical=False
        )

        logger.info("Cleanup tasks registered")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle application close with graceful shutdown (Phase 3).

        Args:
            event: Close event
        """
        # Register cleanup tasks if not already done
        if not hasattr(self, "_cleanup_manager"):
            self._register_cleanup_tasks()

        logger.info("Performing graceful shutdown...")
        success = self._cleanup_manager.cleanup()

        if success:
            logger.info("✅ Shutdown completed successfully")
            event.accept()
        else:
            logger.warning("⚠️ Some critical cleanup tasks failed")
            # Ask user if they want to force quit
            if ask_confirmation(
                self,
                "Shutdown Warning",
                "Some critical cleanup tasks failed. Force quit anyway?",
                confirm_variant="danger",
            ):
                event.accept()
            else:
                event.ignore()


__all__ = ["MainWindow"]
