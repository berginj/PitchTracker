"""Typed host contract shared by the main-window implementation mixins."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from app.services.orchestrator import PipelineOrchestrator
from configs.settings import AppConfig
from detect.config import DetectorConfig, Mode
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
from ui.widgets import PlateMapWidget, RoiLabel


class MainWindowMixinHost(QtWidgets.QMainWindow):
    """Declare state owned by ``MainWindow`` for independently checked mixins."""

    _config_path_value: Path
    _config: AppConfig
    _service: PipelineOrchestrator
    _timer: QtCore.QTimer

    _left_input: QtWidgets.QComboBox
    _right_input: QtWidgets.QComboBox
    _start_button: QtWidgets.QPushButton
    _stop_button: QtWidgets.QPushButton
    _restart_button: QtWidgets.QPushButton
    _record_button: QtWidgets.QPushButton
    _stop_record_button: QtWidgets.QPushButton
    _refresh_button: QtWidgets.QPushButton
    _replay_button: QtWidgets.QPushButton
    _pause_button: QtWidgets.QPushButton
    _step_button: QtWidgets.QPushButton
    _training_button: QtWidgets.QPushButton
    _record_settings_button: QtWidgets.QPushButton
    _strike_settings_button: QtWidgets.QPushButton
    _detector_settings_button: QtWidgets.QPushButton
    _session_name: QtWidgets.QLineEdit
    _profile_combo: QtWidgets.QComboBox
    _profile_load: QtWidgets.QPushButton
    _profile_save: QtWidgets.QPushButton
    _profile_name: QtWidgets.QLineEdit
    _pitcher_combo: QtWidgets.QComboBox
    _pitcher_add: QtWidgets.QPushButton
    _pitcher_name_input: QtWidgets.QLineEdit
    _low_perf_button: QtWidgets.QPushButton
    _cue_card_button: QtWidgets.QPushButton
    _enter_button: QtWidgets.QPushButton
    _checklist_button: QtWidgets.QPushButton
    _output_dir: QtWidgets.QLineEdit
    _output_browse: QtWidgets.QPushButton
    _manual_speed: QtWidgets.QDoubleSpinBox
    _status_label: QtWidgets.QLabel
    _ball_combo: QtWidgets.QComboBox
    _batter_height: QtWidgets.QDoubleSpinBox
    _top_ratio: QtWidgets.QDoubleSpinBox
    _bottom_ratio: QtWidgets.QDoubleSpinBox
    _save_strike_button: QtWidgets.QPushButton
    _health_left: QtWidgets.QLabel
    _health_right: QtWidgets.QLabel
    _calib_summary: QtWidgets.QLabel
    _focus_left: QtWidgets.QLabel
    _focus_right: QtWidgets.QLabel
    _left_view: RoiLabel
    _right_view: RoiLabel
    _plate_map: PlateMapWidget
    _plate_widget: QtWidgets.QWidget
    _views_layout: QtWidgets.QHBoxLayout
    _setup_group: QtWidgets.QGroupBox
    _controls_widget: QtWidgets.QWidget
    _health_panel: QtWidgets.QGroupBox
    _lane_button: QtWidgets.QPushButton
    _lane_right_button: QtWidgets.QPushButton
    _plate_button: QtWidgets.QPushButton
    _clear_lane_button: QtWidgets.QPushButton
    _clear_plate_button: QtWidgets.QPushButton
    _save_roi_button: QtWidgets.QPushButton
    _load_roi_button: QtWidgets.QPushButton
    _guide_button: QtWidgets.QPushButton
    _quick_cal_button: QtWidgets.QPushButton
    _plate_cal_button: QtWidgets.QPushButton
    _mode_combo: QtWidgets.QComboBox
    _frame_diff: QtWidgets.QDoubleSpinBox
    _bg_diff: QtWidgets.QDoubleSpinBox
    _bg_alpha: QtWidgets.QDoubleSpinBox
    _edge_thresh: QtWidgets.QDoubleSpinBox
    _blob_thresh: QtWidgets.QDoubleSpinBox
    _min_area: QtWidgets.QSpinBox
    _min_circ: QtWidgets.QDoubleSpinBox
    _apply_detector: QtWidgets.QPushButton
    _health_toggle_action: QtGui.QAction
    _right_camera_action: QtGui.QAction
    _game_status: QtWidgets.QLabel
    _game_score: QtWidgets.QLabel
    _game_streak_label: QtWidgets.QLabel

    _focus_monitor: FocusMonitorController
    _calibration_overlay: CalibrationOverlayController
    _profile_manager: ProfileManager
    _device_manager: DeviceManager
    _calibration_manager: CalibrationManager
    _export_manager: ExportManager
    _roi_manager: RoiManager
    _replay_controller: ReplayController
    _game_visualizer: GameVisualizer
    _settings_manager: SettingsManager
    _capture_controller: CaptureController
    _recording_controller: RecordingController

    def _config_path(self) -> Path:
        raise NotImplementedError

    def _get_git_commit(self) -> str | None:
        raise NotImplementedError

    def _refresh_devices(self) -> None:
        raise NotImplementedError

    def _load_rois(self) -> None:
        raise NotImplementedError

    def _save_rois(self) -> None:
        raise NotImplementedError

    def _set_roi_mode(self, mode: str) -> None:
        raise NotImplementedError

    def _clear_lane(self) -> None:
        raise NotImplementedError

    def _clear_plate(self) -> None:
        raise NotImplementedError

    def _reset_focus_peaks(self) -> None:
        raise NotImplementedError

    def _restart_capture(self) -> None:
        raise NotImplementedError

    def _start_capture(self) -> None:
        raise NotImplementedError

    def _stop_capture(self) -> None:
        raise NotImplementedError

    def _start_recording(self) -> None:
        raise NotImplementedError

    def _stop_recording(self) -> None:
        raise NotImplementedError

    def _start_training_capture(self) -> None:
        raise NotImplementedError

    def _start_replay(self) -> None:
        raise NotImplementedError

    def _toggle_replay_pause(self) -> None:
        raise NotImplementedError

    def _step_replay(self) -> None:
        raise NotImplementedError

    def _set_manual_speed(self, value: float) -> None:
        raise NotImplementedError

    def _set_output_dir(self, path: str) -> None:
        raise NotImplementedError

    def _save_strike_zone(self) -> None:
        raise NotImplementedError

    def _cue_card_test(self) -> None:
        raise NotImplementedError

    def _set_production_mode(self, enabled: bool) -> None:
        raise NotImplementedError

    def _set_target_mode(self, enabled: bool) -> None:
        raise NotImplementedError

    def _reset_tic_tac_toe_game(self) -> None:
        raise NotImplementedError

    def _apply_low_perf_mode(self) -> None:
        raise NotImplementedError

    def _apply_detector_config(self) -> None:
        raise NotImplementedError

    def _apply_detector_to_service(
        self,
        detector_cfg: DetectorConfig,
        mode: Mode,
        ml_settings: dict[str, object],
    ) -> None:
        raise NotImplementedError

    def _run_calibration_wizard(self) -> None:
        raise NotImplementedError


__all__ = ["MainWindowMixinHost"]
