"""Main window class for PitchTracker application."""

from __future__ import annotations

import json
import os
import platform
import random
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml
from PySide6 import QtCore, QtGui, QtWidgets

from app.pipeline_service import InProcessPipelineService
from calib.plate_plane import estimate_and_write
from configs.app_state import load_state, save_state
from configs.lane_io import load_lane_rois, save_lane_rois
from configs.location_profiles import apply_profile, list_profiles, load_profile, save_profile
from configs.pitchers import add_pitcher, load_pitchers
from configs.roi_io import load_rois, save_rois
from configs.settings import load_config
from configs.validator import validate_config_file
from contracts import Frame, StereoObservation
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
from detect.fiducials import FiducialDetection, detect_apriltags
from detect.lane import LaneRoi
from metrics.strike_zone import build_strike_zone
from exceptions import ConfigValidationError
from ui.device_utils import current_serial, probe_opencv_indices, probe_uvc_devices
from ui.dialogs import (
    CalibrationGuide,
    CalibrationWizardDialog,
    ChecklistDialog,
    DetectorSettingsDialog,
    PlatePlaneDialog,
    QuickCalibrateDialog,
    RecordingSettingsDialog,
    SessionSummaryDialog,
    StartupDialog,
    StrikeZoneSettingsDialog,
)
from ui.drawing import frame_to_pixmap
from ui.export import save_session_export, upload_session
from ui.geometry import (
    Overlay,
    Rect,
    normalize_rect,
    polygon_to_rect,
    rect_to_polygon,
    roi_overlays,
)
from ui.widgets import PlateMapWidget, RoiLabel

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
        self.setWindowTitle("Pitch Tracker")
        self._config_path_value = Path(config_path)

        # Validate configuration before loading (Phase 4)
        self._validate_config_at_startup(self._config_path_value)

        # Load configuration
        self._config = load_config(self._config_path_value)

        # Initialize system hardening (Phase 2-4)
        self._init_error_handling()
        self._init_resource_monitoring()
        self._init_resource_limits()

        self._service = InProcessPipelineService(backend=backend)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_preview)
        self._roi_path = Path("rois/shared_rois.json")
        self._lane_path = Path("rois/shared_lane_rois.json")
        self._lane_rect: Optional[Rect] = None
        self._lane_rect_right: Optional[Rect] = None
        self._plate_rect: Optional[Rect] = None
        self._active_rect: Optional[Rect] = None
        self._roi_mode: Optional[str] = None
        self._replay_capture: Optional[cv2.VideoCapture] = None
        self._replay_frame_index = 0
        self._replay_trail: deque[tuple[int, int]] = deque(maxlen=30)
        self._replay_detector: Optional[ClassicalDetector] = None
        self._replay_paused = False
        self._pitcher_name: Optional[str] = None
        self._location_profile: Optional[str] = None
        self._detection_threading = "per_camera"
        self._detection_workers = 2
        self._detector_type = "classical"
        self._detector_model_path = ""
        self._detector_model_input_size = (640, 640)
        self._detector_model_conf_threshold = 0.25
        self._detector_model_class_id = 0
        self._detector_model_format = "yolo_v5"
        self._calibration_wizard: Optional[CalibrationWizardDialog] = None
        self._show_target_overlay = False
        self._target_found = False
        self._target_corners: Optional[list[tuple[float, float]]] = None
        self._target_stride = 5
        self._target_frame_index = 0
        self._target_pattern = (9, 6)
        self._show_fiducials = False
        self._fiducial_detections: list[FiducialDetection] = []
        self._fiducial_error: Optional[str] = None
        self._fiducial_stride = 5
        self._fiducial_frame_index = 0
        self._fiducial_ids = {"plate": 0, "rubber": 1}

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
        self._status_label.setStyleSheet(
            "QLabel { "
            "background-color: white; "
            "color: black; "
            "padding: 8px; "
            "border: 2px solid #2196F3; "
            "border-radius: 4px; "
            "font-size: 12pt; "
            "font-weight: bold; "
            "}"
        )
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
        self._health_left.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 4px; "
            "border: 1px solid #ccc; font-weight: bold; }"
        )
        self._health_right = QtWidgets.QLabel("R: fps=0.0 jitter=0.0ms drops=0")
        self._health_right.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 4px; "
            "border: 1px solid #ccc; font-weight: bold; }"
        )
        self._calib_summary = QtWidgets.QLabel("Calib: baseline_ft=? f_px=?")
        self._calib_summary.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 4px; "
            "border: 1px solid #ccc; font-weight: bold; }"
        )
        self._focus_left = QtWidgets.QLabel("L Focus: --- (peak: ---)")
        self._focus_left.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 4px; "
            "border: 1px solid #ccc; font-weight: bold; }"
        )
        self._focus_right = QtWidgets.QLabel("R Focus: --- (peak: ---)")
        self._focus_right.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 4px; "
            "border: 1px solid #ccc; font-weight: bold; }"
        )
        self._focus_peak_left = 0.0
        self._focus_peak_right = 0.0

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
        self._recent_pitch_paths: list[list[StereoObservation]] = []
        self._last_pitch_id: Optional[str] = None
        self._tic_tac_toe_board: list[list[str]] = [["", "", ""], ["", "", ""], ["", "", ""]]
        self._game_score_x = 0
        self._game_score_o = 0
        self._game_round = 0
        self._game_streak = 0
        self._production_mode = False
        self._target_mode = False
        self._target_cell: Optional[tuple[int, int]] = None

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
        container.setLayout(layout)
        self.setCentralWidget(container)
        self._build_menu()

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

        self._run_startup_dialog()

    def _start_capture(self) -> None:
        left = current_serial(self._left_input)
        right = current_serial(self._right_input)
        if not left or not right:
            self._status_label.setText("Enter both serials.")
            return
        if not self._pre_capture_check():
            return
        self._stop_replay()
        self._service.start_capture(self._config, left, right, config_path=self._config_path())
        self._status_label.setText("Capturing.")
        self._timer.start(int(1000 / max(self._config.ui.refresh_hz, 1)))

    def _stop_capture(self) -> None:
        self._timer.stop()
        self._service.stop_capture()
        self._status_label.setText("Stopped.")

    def _restart_capture(self) -> None:
        self._stop_capture()
        self._start_capture()

    def _pre_capture_check(self) -> bool:
        errors: list[str] = []
        warnings: list[str] = []
        config_path = self._config_path()
        try:
            validate_config_file(str(config_path))
        except ConfigValidationError as exc:
            errors.append(str(exc))
            for detail in exc.validation_errors:
                errors.append(f"- {detail}")
        if self._config.detector.type == "ml":
            model_path = self._config.detector.model_path
            if not model_path:
                errors.append("ML detector enabled but model_path is empty.")
            else:
                resolved = Path(model_path)
                if not resolved.exists():
                    errors.append(f"ML model not found at {resolved}.")
        output_dir = Path(self._config.recording.output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"Output dir not writable: {output_dir} ({exc})")
        else:
            if not os.access(output_dir, os.W_OK):
                errors.append(f"Output dir not writable: {output_dir}")
        if not self._roi_path.exists():
            warnings.append(f"ROI file {self._roi_path} not found; lane/plate gating will be disabled.")
        if not self._lane_path.exists():
            warnings.append(f"Lane ROI overrides not found at {self._lane_path}; using shared lane ROI for both cameras.")

        if errors:
            QtWidgets.QMessageBox.critical(
                self,
                "Pre-Capture Check Failed",
                "Fix the following before capturing:\n" + "\n".join(errors),
            )
            return False
        if warnings:
            result = QtWidgets.QMessageBox.warning(
                self,
                "Pre-Capture Warnings",
                "Continue with the following warnings?\n" + "\n".join(warnings),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            return result == QtWidgets.QMessageBox.Yes
        return True

    def _start_recording(self) -> None:
        if not self._health_ok():
            QtWidgets.QMessageBox.warning(
                self,
                "Health Check",
                "Health check failed. Verify FPS and drops before recording.",
            )
            return
        session = self._session_name.text().strip() or self._default_session_name()
        if session:
            self._session_name.setText(session)
        self._service.start_recording(session_name=session, mode="review")
        self._status_label.setText("Recording...")

    def _browse_output(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self._set_output_dir(path)

    def _set_output_dir(self, path: str) -> None:
        if not path:
            return
        self._output_dir.setText(path)
        self._service.set_record_directory(Path(path))
        config_path = self._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("recording", {})
        data["recording"]["output_dir"] = path
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))

    def _set_manual_speed(self, value: float) -> None:
        speed = value if value > 0 else None
        self._service.set_manual_speed_mph(speed)

    def _stop_recording(self) -> None:
        bundle = self._service.stop_recording()
        summary = self._service.get_session_summary()
        self._status_label.setText(f"Recorded pitches: {summary.pitch_count}")
        session_dir = self._service.get_session_dir()
        dialog = SessionSummaryDialog(
            self,
            summary,
            lambda: upload_session(
                self,
                summary,
                self._config,
                session_dir,
                self._pitcher_name or "Unknown",
                self._location_profile or "Unknown",
            ),
            lambda export_type: save_session_export(
                self,
                summary,
                session_dir,
                export_type,
                self._config_path(),
                self._roi_path,
                self._pitcher_name or "Unknown",
                self._location_profile or "Unknown",
            ),
            session_dir=session_dir,
        )
        dialog.exec()

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
        state = load_state()
        if self._pitcher_name:
            state["last_pitcher"] = self._pitcher_name
        save_state(state)

    def _refresh_profiles(self) -> None:
        self._profile_combo.clear()
        self._profile_combo.addItems(list_profiles())

    def _refresh_pitchers(self) -> None:
        self._pitcher_combo.clear()
        self._pitcher_combo.addItems(load_pitchers())
        state = load_state()
        last = state.get("last_pitcher")
        if last:
            self._pitcher_combo.setCurrentText(last)

    def _load_profile(self) -> None:
        name = self._profile_combo.currentText().strip()
        if not name:
            return
        try:
            profile = load_profile(name)
        except Exception as exc:  # noqa: BLE001 - show profile errors
            QtWidgets.QMessageBox.warning(self, "Load Profile", str(exc))
            return
        left = str(profile.get("left_serial", ""))
        right = str(profile.get("right_serial", ""))
        if left:
            # Find item by data (serial) instead of text label
            for i in range(self._left_input.count()):
                if self._left_input.itemData(i) == left:
                    self._left_input.setCurrentIndex(i)
                    break
            else:
                # Fallback: try setting text directly (might work for old profiles)
                self._left_input.setCurrentText(left)
        if right:
            # Find item by data (serial) instead of text label
            for i in range(self._right_input.count()):
                if self._right_input.itemData(i) == right:
                    self._right_input.setCurrentIndex(i)
                    break
            else:
                # Fallback: try setting text directly (might work for old profiles)
                self._right_input.setCurrentText(right)
        apply_profile(profile, self._roi_path)
        self._load_rois()
        self._location_profile = name
        self._status_label.setText(f"Loaded profile '{name}'.")
        self._enter_app()

    def _save_profile(self) -> None:
        name = self._profile_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.information(
                self,
                "Save Profile",
                "Enter a profile name.",
            )
            return
        left = current_serial(self._left_input)
        right = current_serial(self._right_input)
        if not left and not right:
            QtWidgets.QMessageBox.information(
                self,
                "Save Profile",
                "Select at least one device before saving.",
            )
            return
        save_profile(name, left or "", right or "", self._roi_path)
        self._refresh_profiles()
        self._profile_name.clear()
        self._location_profile = name
        self._status_label.setText(f"Saved profile '{name}'.")

    def _add_pitcher(self) -> None:
        name = self._pitcher_name_input.text().strip()
        if not name:
            return
        pitchers = add_pitcher(name)
        self._pitcher_combo.clear()
        self._pitcher_combo.addItems(pitchers)
        self._pitcher_combo.setCurrentText(name)
        self._pitcher_name_input.clear()
        self._set_pitcher(name)

    def _set_pitcher(self, name: str) -> None:
        name = name.strip()
        self._pitcher_name = name if name else None

    def _run_startup_dialog(self) -> None:
        dialog = StartupDialog(self)
        result = dialog.exec()
        if result != QtWidgets.QDialog.Accepted:
            return
        profile_name, pitcher = dialog.values()
        if pitcher:
            self._pitcher_name = pitcher
            self._pitcher_combo.setCurrentText(pitcher)
            add_pitcher(pitcher)
        if profile_name:
            self._profile_combo.setCurrentText(profile_name)
            self._location_profile = profile_name
            self._load_profile()
        self._run_calibration_wizard()

    def _run_calibration_wizard(self) -> None:
        if self._calibration_wizard is not None:
            self._calibration_wizard.raise_()
            self._calibration_wizard.activateWindow()
            return
        wizard = CalibrationWizardDialog(self)
        wizard.setModal(False)
        wizard.finished.connect(lambda: setattr(self, "_calibration_wizard", None))
        self._calibration_wizard = wizard
        wizard.show()

    def _cue_card_test(self) -> None:
        try:
            detections = self._service.get_latest_detections()
        except Exception:
            QtWidgets.QMessageBox.information(
                self,
                "Cue Card Test",
                "Start capture to run the cue card test.",
            )
            return
        total = sum(len(items) for items in detections.values())
        QtWidgets.QMessageBox.information(
            self,
            "Cue Card Test",
            f"Detections in current frame: {total}\n"
            "Hold the cue card in the lane and confirm detections appear.",
        )

    def _apply_low_perf_mode(self) -> None:
        if self._timer.isActive():
            QtWidgets.QMessageBox.information(
                self,
                "Low Perf Mode",
                "Stop capture before applying low performance settings.",
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
        pitcher = self._pitcher_name or "pitcher"
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        return f"{pitcher}-{timestamp}"

    def _upload_session(self, summary) -> None:
        if not self._config.upload.enabled:
            QtWidgets.QMessageBox.information(
                self,
                "Upload Session",
                "Uploads are disabled. Enable upload in configs/default.yaml.",
            )
            return
        api_base = self._config.upload.swa_api_base.rstrip("/")
        if not api_base:
            QtWidgets.QMessageBox.warning(
                self,
                "Upload Session",
                "Upload URL is not configured.",
            )
            return
        session_dir = self._service.get_session_dir()
        marker_spec = None
        if session_dir:
            marker_path = Path(session_dir) / "marker_spec.json"
            if marker_path.exists():
                marker_spec = json.loads(marker_path.read_text())
        payload = {
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "session": asdict(summary),
            "metadata": {
                "uploaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pitcher": self._pitcher_name,
                "location_profile": self._location_profile,
                "rig_id": None,
                "source": "PitchTracker",
            },
            "marker_spec": marker_spec,
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{api_base}/sessions"
        headers = {"Content-Type": "application/json"}
        if self._config.upload.api_key:
            headers["x-api-key"] = self._config.upload.api_key
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Upload failed: {response.status}")
        except (urllib.error.URLError, RuntimeError) as exc:
            QtWidgets.QMessageBox.warning(self, "Upload Session", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Upload Session", "Upload complete.")

    def _save_session_export(
        self,
        summary,
        session_dir: Optional[Path],
        export_type: Optional[str],
    ) -> None:
        if session_dir is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Save Session",
                "No session directory available for export.",
            )
            return
        if not export_type:
            QtWidgets.QMessageBox.warning(
                self,
                "Save Session",
                "Select an export type before saving.",
            )
            return

        try:
            if export_type == "summary_json":
                self._export_session_summary_json(summary, session_dir)
            elif export_type == "summary_csv":
                self._export_session_summary_csv(summary, session_dir)
            elif export_type == "training_report":
                self._export_training_report(session_dir)
            elif export_type == "manifests_zip":
                self._export_manifests_zip(session_dir)
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Save Session",
                    f"Unknown export type: {export_type}",
                )
        except Exception as exc:  # noqa: BLE001 - surface export failures
            QtWidgets.QMessageBox.warning(self, "Save Session", str(exc))

    def _export_session_summary_json(self, summary, session_dir: Path) -> None:
        default_name = "session_summary.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Session Summary (JSON)",
            default_name,
            "JSON files (*.json)",
        )
        if not path:
            return
        src = session_dir / "session_summary.json"
        if src.exists():
            shutil.copyfile(src, path)
            return
        payload = asdict(summary)
        payload["schema_version"] = SCHEMA_VERSION
        payload["app_version"] = APP_VERSION
        Path(path).write_text(json.dumps(payload, indent=2))

    def _export_session_summary_csv(self, summary, session_dir: Path) -> None:
        default_name = "session_summary.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Session Summary (CSV)",
            default_name,
            "CSV files (*.csv)",
        )
        if not path:
            return
        src = session_dir / "session_summary.csv"
        if src.exists():
            shutil.copyfile(src, path)
            return
        self._write_session_summary_csv(Path(path), summary)

    def _write_session_summary_csv(self, path: Path, summary) -> None:
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "pitch_id",
                    "t_start_ns",
                    "t_end_ns",
                    "is_strike",
                    "zone_row",
                    "zone_col",
                    "run_in",
                    "rise_in",
                    "speed_mph",
                    "rotation_rpm",
                    "sample_count",
                ]
            )
            for pitch in summary.pitches:
                writer.writerow(
                    [
                        pitch.pitch_id,
                        pitch.t_start_ns,
                        pitch.t_end_ns,
                        int(pitch.is_strike),
                        pitch.zone_row if pitch.zone_row is not None else "",
                        pitch.zone_col if pitch.zone_col is not None else "",
                        f"{pitch.run_in:.3f}",
                        f"{pitch.rise_in:.3f}",
                        f"{pitch.speed_mph:.3f}" if pitch.speed_mph is not None else "",
                        f"{pitch.rotation_rpm:.3f}" if pitch.rotation_rpm is not None else "",
                        pitch.sample_count,
                    ]
                )

    def _export_training_report(self, session_dir: Path) -> None:
        default_name = "training_report.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Training Report",
            default_name,
            "JSON files (*.json)",
        )
        if not path:
            return
        payload = build_training_report(
            session_dir=session_dir,
            config_path=self._config_path(),
            roi_path=self._roi_path,
            source={
                "app": "PitchTracker",
                "rig_id": None,
                "pitcher": self._pitcher_name,
                "location_profile": self._location_profile,
                "operator": None,
                "host": None,
            },
        )
        Path(path).write_text(json.dumps(payload, indent=2))

    def _export_manifests_zip(self, session_dir: Path) -> None:
        default_name = "session_manifests.zip"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Session Manifests",
            default_name,
            "Zip files (*.zip)",
        )
        if not path:
            return
        files: List[Path] = []
        manifest = session_dir / "manifest.json"
        summary_json = session_dir / "session_summary.json"
        summary_csv = session_dir / "session_summary.csv"
        if manifest.exists():
            files.append(manifest)
        if summary_json.exists():
            files.append(summary_json)
        if summary_csv.exists():
            files.append(summary_csv)
        files.extend(session_dir.rglob("*/manifest.json"))
        if not files:
            raise RuntimeError("No manifest files found to export.")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in files:
                archive.write(file_path, file_path.relative_to(session_dir))

    def _start_training_capture(self) -> None:
        if not self._health_ok():
            QtWidgets.QMessageBox.warning(
                self,
                "Health Check",
                "Health check failed. Verify FPS and drops before recording.",
            )
            return
        session = self._session_name.text().strip() or self._default_session_name()
        if session:
            self._session_name.setText(session)
        if not session:
            QtWidgets.QMessageBox.information(
                self,
                "Training Capture",
                "Set a session name before starting training capture.",
            )
            return
        self._service.start_recording(session_name=session, mode="training")
        self._status_label.setText("Training capture...")

    def _update_preview(self) -> None:
        if self._replay_capture is not None:
            self._update_replay()
            return
        try:
            left_frame, right_frame = self._service.get_preview_frames()
        except RuntimeError as exc:
            self._status_label.setText(str(exc))
            return
        self._left_view.set_image_size(left_frame.width, left_frame.height)
        overlays_left = roi_overlays(self._lane_rect, self._plate_rect, self._active_rect)
        lane_right = self._lane_rect_right or self._lane_rect
        overlays_right = roi_overlays(lane_right, self._plate_rect, self._active_rect)
        detections = self._service.get_latest_detections()
        gated = self._service.get_latest_gated_detections()
        left_dets = detections.get(left_frame.camera_id, [])
        right_dets = detections.get(right_frame.camera_id, [])
        left_gated = gated.get(left_frame.camera_id, {})
        right_gated = gated.get(right_frame.camera_id, {})
        strike = self._service.get_strike_result()
        zone = None
        if strike.zone_row is not None and strike.zone_col is not None:
            zone = (strike.zone_row, strike.zone_col)
        checkerboard = None
        if self._show_target_overlay:
            self._target_frame_index += 1
            if self._target_frame_index % self._target_stride == 0:
                gray = (
                    left_frame.image
                    if left_frame.image.ndim == 2
                    else cv2.cvtColor(left_frame.image, cv2.COLOR_BGR2GRAY)
                )
                found, corners = cv2.findChessboardCorners(gray, self._target_pattern)
                self._target_found = bool(found)
                if found and corners is not None:
                    self._target_corners = [
                        (float(pt[0][0]), float(pt[0][1])) for pt in corners
                    ]
                else:
                    self._target_corners = None
            checkerboard = self._target_corners
        fiducials = None
        if self._show_fiducials:
            self._fiducial_frame_index += 1
            if self._fiducial_frame_index % self._fiducial_stride == 0:
                gray = (
                    left_frame.image
                    if left_frame.image.ndim == 2
                    else cv2.cvtColor(left_frame.image, cv2.COLOR_BGR2GRAY)
                )
                detections, error = detect_apriltags(gray)
                self._fiducial_detections = detections
                self._fiducial_error = error
            fiducials = self._fiducial_detections

        # Compute focus scores for both cameras (will be used in health panel and overlay)
        from detect.utils import compute_focus_score
        focus_left = compute_focus_score(left_frame.image)
        focus_right = compute_focus_score(right_frame.image)

        # Show focus overlay when target overlay is active (during calibration)
        focus_overlay_left = focus_left if self._show_target_overlay else None
        focus_overlay_right = focus_right if self._show_target_overlay else None

        self._left_view.setPixmap(
            frame_to_pixmap(
                left_frame.image,
                overlays_left,
                left_dets,
                left_gated.get("lane", []),
                left_gated.get("plate", []),
                plate_rect=self._plate_rect,
                zone=zone,
                checkerboard=checkerboard,
                fiducials=fiducials,
                focus_score=focus_overlay_left,
            )
        )
        if self._right_view.isVisible():
            self._right_view.setPixmap(
                frame_to_pixmap(
                    right_frame.image,
                    overlays_right,
                    right_dets,
                    right_gated.get("lane", []),
                    right_gated.get("plate", []),
                    plate_rect=self._plate_rect,
                    zone=zone,
                    focus_score=focus_overlay_right,
                )
            )
        self._update_plate_map()
        stats = self._service.get_stats()
        plate_metrics = self._service.get_plate_metrics()
        if stats:
            left_stats = stats.get("left", {})
            right_stats = stats.get("right", {})
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

            # Update focus quality tracking (scores already computed above)
            # Track peak values
            if focus_left > self._focus_peak_left:
                self._focus_peak_left = focus_left
            if focus_right > self._focus_peak_right:
                self._focus_peak_right = focus_right

            # Color code based on focus quality (empirical thresholds)
            # Good: >200 (green), Fair: 100-200 (yellow), Poor: <100 (red)
            def focus_color(score: float) -> str:
                if score >= 200:
                    return "#2ecc71"  # Green
                elif score >= 100:
                    return "#f39c12"  # Yellow/Orange
                else:
                    return "#e74c3c"  # Red

            self._focus_left.setText(f"L Focus: {focus_left:.0f} (peak: {self._focus_peak_left:.0f})")
            self._focus_left.setStyleSheet(
                f"QLabel {{ background-color: {focus_color(focus_left)}; color: white; "
                f"padding: 4px; border: 1px solid #ccc; font-weight: bold; }}"
            )

            self._focus_right.setText(f"R Focus: {focus_right:.0f} (peak: {self._focus_peak_right:.0f})")
            self._focus_right.setStyleSheet(
                f"QLabel {{ background-color: {focus_color(focus_right)}; color: white; "
                f"padding: 4px; border: 1px solid #ccc; font-weight: bold; }}"
            )

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
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select left camera video",
            str(Path("recordings")),
            "Video Files (*.avi *.mp4)",
        )
        if not path:
            return
        self._stop_capture()
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            self._status_label.setText("Failed to open replay video.")
            return
        self._replay_capture = capture
        self._replay_frame_index = 0
        self._replay_trail.clear()
        self._init_replay_detector()
        self._replay_paused = False
        self._status_label.setText("Replay mode.")
        self._timer.start(int(1000 / max(self._config.ui.refresh_hz, 1)))

    def _stop_replay(self) -> None:
        if self._replay_capture is not None:
            self._replay_capture.release()
            self._replay_capture = None
        self._replay_frame_index = 0
        self._replay_trail.clear()

    def _init_replay_detector(self) -> None:
        cfg = self._config.detector
        filter_cfg = FilterConfig(
            min_area=cfg.filters.min_area,
            max_area=cfg.filters.max_area,
            min_circularity=cfg.filters.min_circularity,
            max_circularity=cfg.filters.max_circularity,
            min_velocity=cfg.filters.min_velocity,
            max_velocity=cfg.filters.max_velocity,
        )
        detector_cfg = CvDetectorConfig(
            frame_diff_threshold=cfg.frame_diff_threshold,
            bg_diff_threshold=cfg.bg_diff_threshold,
            bg_alpha=cfg.bg_alpha,
            edge_threshold=cfg.edge_threshold,
            blob_threshold=cfg.blob_threshold,
            runtime_budget_ms=cfg.runtime_budget_ms,
            crop_padding_px=cfg.crop_padding_px,
            min_consecutive=cfg.min_consecutive,
            filters=filter_cfg,
        )
        roi_by_camera = None
        if self._lane_rect:
            roi_by_camera = {"replay_left": rect_to_polygon(self._lane_rect)}
        self._replay_detector = ClassicalDetector(
            config=detector_cfg,
            mode=Mode(cfg.mode),
            roi_by_camera=roi_by_camera,
        )

    def _update_replay(self) -> None:
        if self._replay_capture is None:
            return
        if self._replay_paused:
            return
        ok, frame = self._replay_capture.read()
        if not ok:
            self._status_label.setText("Replay finished.")
            self._stop_replay()
            return
        self._replay_frame_index += 1
        height, width = frame.shape[:2]
        if self._config.camera.pixfmt == "GRAY8":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        frame_obj = Frame(
            camera_id="replay_left",
            frame_index=self._replay_frame_index,
            t_capture_monotonic_ns=0,
            image=gray,
            width=width,
            height=height,
            pixfmt=self._config.camera.pixfmt,
        )
        detections = []
        if self._replay_detector is not None:
            detections = self._replay_detector.detect(frame_obj)
        if detections:
            best = max(detections, key=lambda det: det.confidence)
            self._replay_trail.append((int(best.u), int(best.v)))
        overlays = roi_overlays(self._lane_rect, self._plate_rect, self._active_rect)
        pixmap = frame_to_pixmap(
            gray,
            overlays,
            detections,
            lane_detections=[],
            plate_detections=[],
            plate_rect=self._plate_rect,
            zone=None,
            trail=list(self._replay_trail),
        )
        self._left_view.setPixmap(pixmap)
        self._right_view.setPixmap(QtGui.QPixmap())

    def _toggle_replay_pause(self) -> None:
        if self._replay_capture is None:
            return
        self._replay_paused = not self._replay_paused
        self._status_label.setText("Replay paused." if self._replay_paused else "Replay mode.")

    def _step_replay(self) -> None:
        if self._replay_capture is None:
            return
        self._replay_paused = True
        self._update_replay()

    def _refresh_devices(self) -> None:
        from ui.device_utils import is_arducam_device

        self._left_input.clear()
        self._right_input.clear()

        if self._service._backend == "uvc":
            devices = probe_uvc_devices()  # Already sorted with ArduCam first
            arducam_count = sum(1 for d in devices if is_arducam_device(d.get('friendly_name', '')))

            for device in devices:
                label = f"{device['serial']} - {device['friendly_name']}"
                self._left_input.addItem(label, device["serial"])
                self._right_input.addItem(label, device["serial"])
            if devices:
                status = f"Found {len(devices)} usable device(s)"
                if arducam_count > 0:
                    status += f" ({arducam_count} ArduCam)"
                self._status_label.setText(status + ".")
                if len(devices) >= 2:
                    self._left_input.setCurrentIndex(0)
                    self._right_input.setCurrentIndex(1)
            else:
                self._status_label.setText("No UVC devices found.")
            return

        # OpenCV backend - get friendly names to identify ArduCam devices
        uvc_devices = probe_uvc_devices()
        uvc_by_index = {i: dev for i, dev in enumerate(uvc_devices)}
        indices = probe_opencv_indices()
        arducam_count = 0

        for index in indices:
            # Get friendly name if available
            friendly_name = ""
            if index in uvc_by_index:
                friendly_name = uvc_by_index[index].get('friendly_name', '')
                if is_arducam_device(friendly_name):
                    arducam_count += 1

            label = f"{friendly_name}" if friendly_name else f"Index {index}"
            self._left_input.addItem(label, str(index))
            self._right_input.addItem(label, str(index))

        if indices:
            status = f"Found {len(indices)} camera index(es)"
            if arducam_count > 0:
                status += f" ({arducam_count} ArduCam)"
            self._status_label.setText(status + ".")
            if len(indices) >= 2:
                self._left_input.setCurrentIndex(0)
                self._right_input.setCurrentIndex(1)
        else:
            self._status_label.setText("No OpenCV camera indices available.")

    def _set_roi_mode(self, mode: str) -> None:
        self._roi_mode = mode
        if mode == "lane_right":
            self._left_view.set_mode(None)
            self._right_view.set_mode(mode)
            self._status_label.setText("ROI mode: lane_right (drag rectangle on right view)")
        else:
            self._left_view.set_mode(mode)
            self._right_view.set_mode(None)
            self._status_label.setText(f"ROI mode: {mode} (drag rectangle on left view)")

    def _on_rect_update(self, rect: Rect, final: bool) -> None:
        rect = normalize_rect(rect, self._left_view.image_size())
        if rect is None:
            return
        if final:
            if self._roi_mode == "lane":
                self._lane_rect = rect
            elif self._roi_mode == "plate":
                self._plate_rect = rect
            self._active_rect = None
        else:
            self._active_rect = rect

    def _on_right_rect_update(self, rect: Rect, final: bool) -> None:
        rect = normalize_rect(rect, self._right_view.image_size())
        if rect is None:
            return
        if final:
            if self._roi_mode == "lane_right":
                self._lane_rect_right = rect
            self._active_rect = None
        else:
            self._active_rect = rect

    def _clear_lane(self) -> None:
        self._lane_rect = None
        self._lane_rect_right = None
        self._status_label.setText("Lane ROI cleared.")

    def _clear_plate(self) -> None:
        self._plate_rect = None
        self._status_label.setText("Plate ROI cleared.")

    def _reset_focus_peaks(self) -> None:
        """Reset focus quality peak tracking.

        Useful when adjusting lens focus - reset to start tracking from scratch.
        """
        self._focus_peak_left = 0.0
        self._focus_peak_right = 0.0
        self._status_label.setText("Focus peak values reset. Adjust lenses and watch for green.")

    def _save_rois(self) -> None:
        lane_poly = rect_to_polygon(self._lane_rect)
        lane_right_poly = rect_to_polygon(self._lane_rect_right) if self._lane_rect_right else None
        plate_poly = rect_to_polygon(self._plate_rect)
        save_rois(self._roi_path, lane_poly, plate_poly)
        if lane_poly is not None:
            left_id = current_serial(self._left_input) or "left"
            right_id = current_serial(self._right_input) or "right"
            lane_rois = {
                left_id: LaneRoi(polygon=lane_poly),
                right_id: LaneRoi(polygon=lane_right_poly or lane_poly),
            }
            save_lane_rois(self._lane_path, lane_rois)
        self._status_label.setText("ROIs saved.")

    def _load_rois(self) -> None:
        rois = load_rois(self._roi_path)
        self._lane_rect = polygon_to_rect(rois.get("lane"))
        self._plate_rect = polygon_to_rect(rois.get("plate"))
        self._lane_rect_right = None
        lane_rois = load_lane_rois(self._lane_path)
        left_id = current_serial(self._left_input) or "left"
        right_id = current_serial(self._right_input) or "right"
        if lane_rois:
            left_lane = lane_rois.get(left_id) or lane_rois.get("left")
            right_lane = lane_rois.get(right_id) or lane_rois.get("right")
            if left_lane:
                self._lane_rect = polygon_to_rect(left_lane.polygon)
            if right_lane:
                self._lane_rect_right = polygon_to_rect(right_lane.polygon)
        if self._lane_rect or self._plate_rect:
            self._status_label.setText("ROIs loaded.")

    def _load_detector_defaults(self) -> None:
        cfg = self._config.detector
        self._detector_type = cfg.type
        self._detector_model_path = cfg.model_path or ""
        self._detector_model_input_size = tuple(cfg.model_input_size)
        self._detector_model_conf_threshold = float(cfg.model_conf_threshold)
        self._detector_model_class_id = int(cfg.model_class_id)
        self._detector_model_format = cfg.model_format
        self._mode_combo.setCurrentText(cfg.mode)
        self._frame_diff.setValue(cfg.frame_diff_threshold)
        self._bg_diff.setValue(cfg.bg_diff_threshold)
        self._bg_alpha.setValue(cfg.bg_alpha)
        self._edge_thresh.setValue(cfg.edge_threshold)
        self._blob_thresh.setValue(cfg.blob_threshold)
        self._min_area.setValue(cfg.filters.min_area)
        self._min_circ.setValue(cfg.filters.min_circularity)

    def _apply_detector_config(self) -> None:
        cfg = self._config.detector
        if self._detector_type == "ml" and not self._detector_model_path:
            QtWidgets.QMessageBox.warning(
                self,
                "Detector Settings",
                "Select an ONNX model path before enabling ML detection.",
            )
            return
        filter_cfg = FilterConfig(
            min_area=self._min_area.value(),
            max_area=cfg.filters.max_area,
            min_circularity=self._min_circ.value(),
            max_circularity=cfg.filters.max_circularity,
            min_velocity=cfg.filters.min_velocity,
            max_velocity=cfg.filters.max_velocity,
        )
        detector_cfg = CvDetectorConfig(
            frame_diff_threshold=self._frame_diff.value(),
            bg_diff_threshold=self._bg_diff.value(),
            bg_alpha=self._bg_alpha.value(),
            edge_threshold=self._edge_thresh.value(),
            blob_threshold=self._blob_thresh.value(),
            runtime_budget_ms=cfg.runtime_budget_ms,
            min_consecutive=cfg.min_consecutive,
            filters=filter_cfg,
        )
        mode = Mode(self._mode_combo.currentText())
        self._service.set_detector_config(
            detector_cfg,
            mode,
            detector_type=self._detector_type,
            model_path=self._detector_model_path or None,
            model_input_size=self._detector_model_input_size,
            model_conf_threshold=self._detector_model_conf_threshold,
            model_class_id=self._detector_model_class_id,
            model_format=self._detector_model_format,
        )
        self._service.set_detection_threading(
            self._detection_threading, self._detection_workers
        )
        self._status_label.setText("Detector settings applied.")

    def _set_ball_type(self, ball_type: str) -> None:
        self._service.set_ball_type(ball_type)

    def _set_batter_height(self, value: float) -> None:
        self._service.set_batter_height_in(value)
        self._update_plate_map_zone()

    def _set_strike_ratios(self) -> None:
        self._service.set_strike_zone_ratios(
            self._top_ratio.value(),
            self._bottom_ratio.value(),
        )
        self._update_plate_map_zone()

    def _save_strike_zone(self) -> None:
        config_path = self._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("strike_zone", {})
        data["strike_zone"]["batter_height_in"] = float(self._batter_height.value())
        data["strike_zone"]["top_ratio"] = float(self._top_ratio.value())
        data["strike_zone"]["bottom_ratio"] = float(self._bottom_ratio.value())
        data.setdefault("ball", {})
        data["ball"]["type"] = self._ball_combo.currentText()
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))
        self._status_label.setText("Strike zone saved.")
        self._update_plate_map_zone()

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
        zone = build_strike_zone(
            plate_z_ft=self._config.metrics.plate_plane_z_ft,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
            batter_height_in=self._config.strike_zone.batter_height_in,
            top_ratio=self._config.strike_zone.top_ratio,
            bottom_ratio=self._config.strike_zone.bottom_ratio,
        )
        self._plate_map.set_zone(zone)

    def _update_plate_map(self) -> None:
        paths = self._service.get_recent_pitch_paths()
        self._recent_pitch_paths = paths
        self._plate_map.set_pitch_paths(paths)
        summary = self._service.get_session_summary()
        if summary.pitches:
            last_pitch = summary.pitches[-1]
            if last_pitch.pitch_id != self._last_pitch_id:
                self._last_pitch_id = last_pitch.pitch_id
                if self._target_mode:
                    self._apply_target_mode(last_pitch)
                else:
                    self._apply_pitch_to_tic_tac_toe(last_pitch)
                self._plate_map.set_board(self._tic_tac_toe_board)
                self._update_game_labels()
            crossing = _pitch_crossing_xy(last_pitch)
            self._plate_map.set_crossing_point(crossing)
        else:
            self._plate_map.set_crossing_point(None)

    def _apply_pitch_to_tic_tac_toe(self, pitch) -> None:
        row = pitch.zone_row
        col = pitch.zone_col
        if row is not None and col is not None:
            r = max(1, min(3, row)) - 1
            c = max(1, min(3, col)) - 1
            if self._tic_tac_toe_board[r][c] == "":
                self._tic_tac_toe_board[r][c] = "X"
            else:
                self._mark_tic_tac_toe_ai()
        else:
            self._mark_tic_tac_toe_ai()
        winner = _tic_tac_toe_winner(self._tic_tac_toe_board)
        if winner:
            self._game_round += 1
            if winner == "X":
                self._game_score_x += 1
                self._game_streak += 1
                self._game_status.setText("Win! Keep the streak alive.")
            elif winner == "O":
                self._game_score_o += 1
                self._game_streak = 0
                self._game_status.setText("AI takes the round.")
            else:
                self._game_streak = 0
                self._game_status.setText("Draw round.")
            self._tic_tac_toe_board = [["", "", ""], ["", "", ""], ["", "", ""]]

    def _mark_tic_tac_toe_ai(self) -> None:
        empty = [
            (r, c)
            for r in range(3)
            for c in range(3)
            if self._tic_tac_toe_board[r][c] == ""
        ]
        if not empty:
            return
        r, c = random.choice(empty)
        self._tic_tac_toe_board[r][c] = "O"

    def _reset_tic_tac_toe_game(self) -> None:
        self._tic_tac_toe_board = [["", "", ""], ["", "", ""], ["", "", ""]]
        self._game_score_x = 0
        self._game_score_o = 0
        self._game_round = 0
        self._game_streak = 0
        self._game_status.setText("Ready.")
        self._plate_map.set_board(self._tic_tac_toe_board)
        self._target_cell = None
        self._plate_map.set_target_cell(None)
        self._update_game_labels()

    def _update_game_labels(self) -> None:
        self._game_score.setText(f"Score X:{self._game_score_x}  O:{self._game_score_o}  R:{self._game_round}")
        self._game_streak_label.setText(f"Streak: {self._game_streak}")

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
        self._target_mode = enabled
        if enabled:
            self._target_cell = self._random_target_cell()
            self._game_status.setText("Hit the highlighted target.")
            self._plate_map.set_target_cell(self._target_cell)
        else:
            self._target_cell = None
            self._plate_map.set_target_cell(None)

    def _apply_target_mode(self, pitch) -> None:
        if not self._target_mode or self._target_cell is None:
            return
        row = pitch.zone_row
        col = pitch.zone_col
        if row is None or col is None:
            self._game_streak = 0
            self._game_status.setText("Missed. New target.")
        else:
            cell = (max(1, min(3, row)) - 1, max(1, min(3, col)) - 1)
            if cell == self._target_cell:
                self._game_score_x += 1
                self._game_streak += 1
                self._game_status.setText("Target hit!")
            else:
                self._game_streak = 0
                self._game_status.setText("Missed. New target.")
        self._game_round += 1
        self._target_cell = self._random_target_cell()
        self._plate_map.set_target_cell(self._target_cell)

    def _random_target_cell(self) -> tuple[int, int]:
        return (random.randint(0, 2), random.randint(0, 2))

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        capture_menu = menu_bar.addMenu("Capture")
        start_action = capture_menu.addAction("Start Capture")
        stop_action = capture_menu.addAction("Stop Capture")
        restart_action = capture_menu.addAction("Restart Capture")
        capture_menu.addSeparator()
        record_action = capture_menu.addAction("Start Recording")
        stop_record_action = capture_menu.addAction("Stop Recording")
        capture_menu.addSeparator()
        training_action = capture_menu.addAction("Training Capture")
        start_action.triggered.connect(self._start_capture)
        stop_action.triggered.connect(self._stop_capture)
        restart_action.triggered.connect(self._restart_capture)
        record_action.triggered.connect(self._start_recording)
        stop_record_action.triggered.connect(self._stop_recording)
        training_action.triggered.connect(self._start_training_capture)

        calibration_menu = menu_bar.addMenu("Calibration")
        guide_action = calibration_menu.addAction("Calibration Guide")
        wizard_action = calibration_menu.addAction("Calibration Wizard")
        quick_action = calibration_menu.addAction("Quick Calibrate")
        plate_action = calibration_menu.addAction("Plate Plane Calibrate")
        guide_action.triggered.connect(self._open_calibration_guide)
        wizard_action.triggered.connect(self._run_calibration_wizard)
        quick_action.triggered.connect(self._open_quick_calibrate)
        plate_action.triggered.connect(self._open_plate_calibrate)

        roi_menu = menu_bar.addMenu("ROI")
        lane_action = roi_menu.addAction("Edit Lane ROI")
        lane_right_action = roi_menu.addAction("Edit Right Lane ROI")
        plate_roi_action = roi_menu.addAction("Edit Plate ROI")
        roi_menu.addSeparator()
        clear_lane_action = roi_menu.addAction("Clear Lane ROI")
        clear_plate_action = roi_menu.addAction("Clear Plate ROI")
        roi_menu.addSeparator()
        save_roi_action = roi_menu.addAction("Save ROIs")
        load_roi_action = roi_menu.addAction("Load ROIs")
        lane_action.triggered.connect(lambda: self._set_roi_mode("lane"))
        lane_right_action.triggered.connect(lambda: self._set_roi_mode("lane_right"))
        plate_roi_action.triggered.connect(lambda: self._set_roi_mode("plate"))
        clear_lane_action.triggered.connect(self._clear_lane)
        clear_plate_action.triggered.connect(self._clear_plate)
        save_roi_action.triggered.connect(self._save_rois)
        load_roi_action.triggered.connect(self._load_rois)

        settings_menu = menu_bar.addMenu("Settings")
        record_settings_action = settings_menu.addAction("Recording Settings")
        strike_settings_action = settings_menu.addAction("Strike Zone Settings")
        detector_settings_action = settings_menu.addAction("Detector Settings")
        record_settings_action.triggered.connect(self._open_record_settings)
        strike_settings_action.triggered.connect(self._open_strike_settings)
        detector_settings_action.triggered.connect(self._open_detector_settings)

        tools_menu = menu_bar.addMenu("Tools")
        refresh_action = tools_menu.addAction("Refresh Devices")
        checklist_action = tools_menu.addAction("Checklist")
        low_perf_action = tools_menu.addAction("Low Perf Mode")
        cue_card_action = tools_menu.addAction("Cue Card Test")
        reset_game_action = tools_menu.addAction("Reset Game")
        target_mode_action = tools_menu.addAction("Target Mode")
        target_mode_action.setCheckable(True)
        target_mode_action.setChecked(False)
        refresh_action.triggered.connect(self._refresh_devices)
        checklist_action.triggered.connect(self._open_checklist)
        low_perf_action.triggered.connect(self._apply_low_perf_mode)
        cue_card_action.triggered.connect(self._cue_card_test)
        reset_game_action.triggered.connect(self._reset_tic_tac_toe_game)
        target_mode_action.toggled.connect(self._set_target_mode)

        review_menu = menu_bar.addMenu("Review")
        replay_action = review_menu.addAction("Replay")
        pause_action = review_menu.addAction("Pause/Resume Replay")
        step_action = review_menu.addAction("Step Replay")
        replay_action.triggered.connect(self._start_replay)
        pause_action.triggered.connect(self._toggle_replay_pause)
        step_action.triggered.connect(self._step_replay)

        view_menu = menu_bar.addMenu("View")
        self._health_toggle_action = QtGui.QAction("Show Health Panel", self)
        self._health_toggle_action.setCheckable(True)
        self._health_toggle_action.setChecked(True)
        self._health_toggle_action.toggled.connect(self._health_panel.setVisible)
        view_menu.addAction(self._health_toggle_action)
        self._right_camera_action = QtGui.QAction("Show Right Camera", self)
        self._right_camera_action.setCheckable(True)
        self._right_camera_action.setChecked(False)
        self._right_camera_action.toggled.connect(self._right_view.setVisible)
        view_menu.addAction(self._right_camera_action)
        self._production_action = QtGui.QAction("Production Mode", self)
        self._production_action.setCheckable(True)
        self._production_action.setChecked(False)
        self._production_action.toggled.connect(self._set_production_mode)
        view_menu.addAction(self._production_action)

    def _build_health_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Health")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._health_left)
        layout.addWidget(self._health_right)
        layout.addWidget(self._focus_left)
        layout.addWidget(self._focus_right)

        # Add button to reset focus peak tracking
        reset_focus_btn = QtWidgets.QPushButton("Reset Focus Peaks")
        reset_focus_btn.clicked.connect(self._reset_focus_peaks)
        reset_focus_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px; }")
        layout.addWidget(reset_focus_btn)

        layout.addWidget(self._calib_summary)
        panel.setLayout(layout)
        return panel

    def _build_game_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Game")
        layout = QtWidgets.QVBoxLayout()
        self._game_status = QtWidgets.QLabel("Ready.")
        self._game_status.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 6px; "
            "border: 1px solid #ccc; font-weight: bold; font-size: 11pt; }"
        )
        self._game_score = QtWidgets.QLabel("Score X:0  O:0  R:0")
        self._game_score.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 6px; "
            "border: 1px solid #ccc; font-weight: bold; font-size: 11pt; }"
        )
        self._game_streak_label = QtWidgets.QLabel("Streak: 0")
        self._game_streak_label.setStyleSheet(
            "QLabel { background-color: white; color: black; padding: 6px; "
            "border: 1px solid #ccc; font-weight: bold; font-size: 11pt; }"
        )
        reset = QtWidgets.QPushButton("Reset Game")
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
        dialog = CalibrationGuide(self)
        dialog.exec()

    def _open_quick_calibrate(self) -> None:
        dialog = QuickCalibrateDialog(self, self._config_path())
        dialog.exec()
        if dialog.updated:
            self._config = load_config(self._config_path())
            self._update_calib_summary()
            if dialog.updates:
                baseline = dialog.updates.get("baseline_ft")
                focal = dialog.updates.get("focal_length_px")
                if isinstance(baseline, (int, float)) and isinstance(focal, (int, float)):
                    self._status_label.setText(
                        f"Calibration updated (baseline_ft={baseline:.3f}, f_px={focal:.1f}). Restart capture."
                    )
                else:
                    self._status_label.setText("Calibration updated. Restart capture to apply.")
            else:
                self._status_label.setText("Calibration updated. Restart capture to apply.")

    def _open_plate_calibrate(self) -> None:
        dialog = PlatePlaneDialog(self, self._config_path())
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        left_path, right_path = dialog.values()
        try:
            plate_z = estimate_and_write(Path(left_path), Path(right_path), self._config_path())
        except Exception as exc:  # noqa: BLE001 - show errors
            QtWidgets.QMessageBox.critical(self, "Plate Plane Calibrate", str(exc))
            return
        self._config = load_config(self._config_path())
        self._status_label.setText(
            f"Plate plane updated (Z={plate_z:.3f} ft). Restart capture."
        )

    def _update_calib_summary(self) -> None:
        baseline = self._config.stereo.baseline_ft
        focal = self._config.stereo.focal_length_px
        self._calib_summary.setText(
            f"Calib: baseline_ft={baseline:.3f} f_px={focal:.1f}"
        )

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
        dialog = StrikeZoneSettingsDialog(
            self,
            ball_type=self._ball_combo.currentText(),
            batter_height=self._batter_height.value(),
            top_ratio=self._top_ratio.value(),
            bottom_ratio=self._bottom_ratio.value(),
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            ball_type, height, top_ratio, bottom_ratio = dialog.values()
            self._ball_combo.setCurrentText(ball_type)
            self._batter_height.setValue(height)
            self._top_ratio.setValue(top_ratio)
            self._bottom_ratio.setValue(bottom_ratio)
            self._save_strike_zone()

    def _open_detector_settings(self) -> None:
        dialog = DetectorSettingsDialog(
            self,
            mode=self._mode_combo.currentText(),
            frame_diff=self._frame_diff.value(),
            bg_diff=self._bg_diff.value(),
            bg_alpha=self._bg_alpha.value(),
            edge_thresh=self._edge_thresh.value(),
            blob_thresh=self._blob_thresh.value(),
            min_area=self._min_area.value(),
            min_circ=self._min_circ.value(),
            threading_mode=self._detection_threading,
            worker_count=self._detection_workers,
            detector_type=self._detector_type,
            model_path=self._detector_model_path,
            model_input_size=self._detector_model_input_size,
            model_conf_threshold=self._detector_model_conf_threshold,
            model_class_id=self._detector_model_class_id,
            model_format=self._detector_model_format,
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            values = dialog.values()
            self._mode_combo.setCurrentText(values["mode"])
            self._frame_diff.setValue(values["frame_diff"])
            self._bg_diff.setValue(values["bg_diff"])
            self._bg_alpha.setValue(values["bg_alpha"])
            self._edge_thresh.setValue(values["edge_thresh"])
            self._blob_thresh.setValue(values["blob_thresh"])
            self._min_area.setValue(values["min_area"])
            self._min_circ.setValue(values["min_circ"])
            self._detection_threading = values["threading_mode"]
            self._detection_workers = values["worker_count"]
            self._detector_type = values["detector_type"]
            self._detector_model_path = values["model_path"]
            self._detector_model_input_size = values["model_input_size"]
            self._detector_model_conf_threshold = values["model_conf_threshold"]
            self._detector_model_class_id = values["model_class_id"]
            self._detector_model_format = values["model_format"]
            self._apply_detector_config()

    def _set_target_overlay(self, enabled: bool) -> None:
        self._show_target_overlay = enabled
        self._target_found = False
        self._target_corners = None

    def _set_fiducial_overlay(self, enabled: bool) -> None:
        self._show_fiducials = enabled
        self._fiducial_detections = []
        self._fiducial_error = None

    def _propose_right_lane(self) -> None:
        if self._lane_rect is None:
            QtWidgets.QMessageBox.information(
                self,
                "Propose Right Lane",
                "Draw the left lane ROI first.",
            )
            return
        with self._latest_lock:
            left_frame = self._left_latest
            right_frame = self._right_latest
        if left_frame is None or right_frame is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Propose Right Lane",
                "Start capture before proposing the right lane.",
            )
            return
        left_w, left_h = left_frame.width, left_frame.height
        right_w, right_h = right_frame.width, right_frame.height
        x1, y1, x2, y2 = self._lane_rect
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
            left_id = current_serial(self._left_input)
            right_id = current_serial(self._right_input)
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
        self._lane_rect_right = (rx1, ry1, rx2, ry2)
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
                QtWidgets.QMessageBox.critical(
                    None,
                    "Configuration Error",
                    f"Configuration validation failed:\n\n{error_text}\n\n"
                    f"Please fix these errors in {config_path}",
                )
                import sys
                sys.exit(1)

            # Show warnings (non-blocking)
            warnings = [i for i in issues if i.severity == "warning"]
            if warnings:
                warning_text = "\n".join([f"• {w.field}: {w.message}" for w in warnings])
                QtWidgets.QMessageBox.warning(
                    None,
                    "Configuration Warnings",
                    f"Configuration has warnings:\n\n{warning_text}\n\n"
                    f"The application will continue, but you may want to review these.",
                )

        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                None,
                "Configuration Error",
                f"Failed to validate configuration:\n\n{exc}",
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
            reply = QtWidgets.QMessageBox.question(
                self,
                "Shutdown Warning",
                "Some critical cleanup tasks failed. Force quit anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()



def _tic_tac_toe_winner(board: list[list[str]]) -> Optional[str]:
    lines = []
    for i in range(3):
        lines.append(board[i])
        lines.append([board[0][i], board[1][i], board[2][i]])
    lines.append([board[0][0], board[1][1], board[2][2]])
    lines.append([board[0][2], board[1][1], board[2][0]])
    for line in lines:
        if line[0] and line[0] == line[1] == line[2]:
            return line[0]
    if all(cell for row in board for cell in row):
        return "Draw"
    return None


def _pitch_crossing_xy(pitch) -> Optional[tuple[float, float]]:
    x = getattr(pitch, "trajectory_plate_x_ft", None)
    y = getattr(pitch, "trajectory_plate_y_ft", None)
    if x is None or y is None:
        return None
    return (x, y)


__all__ = ["MainWindow"]
