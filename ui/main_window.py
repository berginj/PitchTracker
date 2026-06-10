"""Main window class for PitchTracker application."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from app.services.orchestrator import PipelineOrchestrator
from configs.settings import load_config
from contracts.versioning import APP_VERSION
from detect.config import Mode
from metrics.strike_zone import build_strike_zone
from ui.main_window_actions import MainWindowActionsMixin
from ui.main_window_menu import MainWindowMenuMixin
from ui.main_window_system import MainWindowSystemMixin
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
from ui.themes import apply_standard_layout, get_style_manager
from app.ui.error_notification import ErrorNotificationWidget, ErrorNotificationBridge
from log_config.logger import get_logger

logger = get_logger(__name__)


class MainWindow(
    MainWindowActionsMixin,
    MainWindowMenuMixin,
    MainWindowSystemMixin,
    QtWidgets.QMainWindow,
):
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
            start_capture_service=lambda cfg, left, right, path: self._service.start_capture(
                cfg, left, right, config_path=path
            ),
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


__all__ = ["MainWindow"]
