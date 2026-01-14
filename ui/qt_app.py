"""PySide6 UI for preview and recording via the pipeline service."""

from __future__ import annotations

import argparse
import time
import json
import urllib.request
import urllib.error
import shutil
import zipfile
import csv
from dataclasses import asdict
from collections import deque
from pathlib import Path
from typing import Optional, List

import cv2
import yaml
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.pipeline_service import InProcessPipelineService
from calib.quick_calibrate import calibrate_and_write
from calib.plate_plane import estimate_and_write
from capture.uvc_backend import list_uvc_devices
from configs.lane_io import save_lane_rois
from configs.roi_io import load_rois, save_rois
from configs.location_profiles import apply_profile, list_profiles, load_profile, save_profile
from configs.pitchers import add_pitcher, load_pitchers
from configs.app_state import load_state, save_state
from configs.settings import load_config
from detect.lane import LaneRoi
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
from detect.classical_detector import ClassicalDetector
from record.training_report import build_training_report
from contracts import Frame
from contracts.versioning import APP_VERSION, SCHEMA_VERSION


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pitch Tracker Qt UI.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--backend", default="uvc", choices=("uvc", "opencv", "sim"))
    return parser.parse_args()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, backend: str, config_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("Pitch Tracker")
        self._config = load_config(config_path)
        self._service = InProcessPipelineService(backend=backend)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_preview)
        self._roi_path = Path("configs/roi.json")
        self._lane_path = Path("configs/lane_roi.json")
        self._lane_rect: Optional[Rect] = None
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
        self._health_right = QtWidgets.QLabel("R: fps=0.0 jitter=0.0ms drops=0")
        self._calib_summary = QtWidgets.QLabel("Calib: baseline_ft=? f_px=?")

        self._left_view = RoiLabel(self._on_rect_update)
        self._right_view = QtWidgets.QLabel()
        self._left_view.setMinimumSize(320, 180)
        self._right_view.setMinimumSize(320, 180)
        self._left_view.setAlignment(QtCore.Qt.AlignCenter)
        self._right_view.setAlignment(QtCore.Qt.AlignCenter)
        self._left_view.setScaledContents(True)
        self._right_view.setScaledContents(True)

        self._lane_button = QtWidgets.QPushButton("Edit Lane ROI")
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
        controls.addWidget(self._start_button)
        controls.addWidget(self._stop_button)
        controls.addWidget(self._restart_button)
        controls.addWidget(self._record_button)
        controls.addWidget(self._stop_record_button)
        controls.addWidget(self._training_button)
        controls.addWidget(self._replay_button)
        controls.addWidget(self._pause_button)
        controls.addWidget(self._step_button)
        controls.addWidget(self._record_settings_button)
        controls.addWidget(self._strike_settings_button)
        controls.addWidget(self._detector_settings_button)
        controls.addWidget(self._checklist_button)

        views = QtWidgets.QHBoxLayout()
        views.addWidget(self._left_view, 1)
        views.addWidget(self._right_view, 1)

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
        device_row.addWidget(self._refresh_button)
        roi_row = QtWidgets.QHBoxLayout()
        roi_row.addWidget(self._lane_button)
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
        action_row.addWidget(self._low_perf_button)
        action_row.addWidget(self._cue_card_button)
        action_row.addStretch(1)
        action_row.addWidget(self._enter_button)
        setup_layout = QtWidgets.QVBoxLayout()
        setup_layout.addLayout(profile_row)
        setup_layout.addLayout(pitcher_row)
        setup_layout.addLayout(device_row)
        setup_layout.addLayout(roi_row)
        setup_layout.addLayout(calib_row)
        setup_layout.addLayout(action_row)
        self._setup_group.setLayout(setup_layout)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._setup_group)
        layout.addLayout(controls)
        layout.addLayout(views)
        layout.addWidget(self._build_health_panel())
        layout.addWidget(self._status_label)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

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
        self._update_calib_summary()
        self._set_setup_mode(True)
        self._run_startup_dialog()

    def _start_capture(self) -> None:
        left = _current_serial(self._left_input)
        right = _current_serial(self._right_input)
        if not left or not right:
            self._status_label.setText("Enter both serials.")
            return
        self._service.start_capture(self._config, left, right)
        self._status_label.setText("Capturing.")
        self._timer.start(int(1000 / max(self._config.ui.refresh_hz, 1)))

    def _stop_capture(self) -> None:
        self._timer.stop()
        self._service.stop_capture()
        self._status_label.setText("Stopped.")

    def _restart_capture(self) -> None:
        self._stop_capture()
        self._start_capture()

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
            self._upload_session,
            lambda export_type: self._save_session_export(summary, session_dir, export_type),
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
            self._left_input.setCurrentText(left)
        if right:
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
        left = _current_serial(self._left_input)
        right = _current_serial(self._right_input)
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
        overlays = _roi_overlays(self._lane_rect, self._plate_rect, self._active_rect)
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
        self._left_view.setPixmap(
            _frame_to_pixmap(
                left_frame.image,
                overlays,
                left_dets,
                left_gated.get("lane", []),
                left_gated.get("plate", []),
                plate_rect=self._plate_rect,
                zone=zone,
            )
        )
        self._right_view.setPixmap(
            _frame_to_pixmap(
                right_frame.image,
                overlays,
                right_dets,
                right_gated.get("lane", []),
                right_gated.get("plate", []),
                plate_rect=self._plate_rect,
                zone=zone,
            )
        )
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
            roi_by_camera = {"replay_left": _rect_to_polygon(self._lane_rect)}
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
        overlays = _roi_overlays(self._lane_rect, self._plate_rect, self._active_rect)
        pixmap = _frame_to_pixmap(
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
        self._left_input.clear()
        self._right_input.clear()
        if self._service._backend == "uvc":
            devices = _probe_uvc_devices()
            for device in devices:
                label = f"{device['serial']} - {device['friendly_name']}"
                self._left_input.addItem(label, device["serial"])
                self._right_input.addItem(label, device["serial"])
            if devices:
                self._status_label.setText(f"Found {len(devices)} usable device(s).")
                if len(devices) >= 2:
                    self._left_input.setCurrentIndex(0)
                    self._right_input.setCurrentIndex(1)
            else:
                self._status_label.setText("No UVC devices found.")
            return
        indices = _probe_opencv_indices()
        for index in indices:
            label = f"Index {index}"
            self._left_input.addItem(label, str(index))
            self._right_input.addItem(label, str(index))
        if indices:
            self._status_label.setText(f"Found {len(indices)} camera index(es).")
            if len(indices) >= 2:
                self._left_input.setCurrentIndex(0)
                self._right_input.setCurrentIndex(1)
        else:
            self._status_label.setText("No OpenCV camera indices available.")

    def _set_roi_mode(self, mode: str) -> None:
        self._roi_mode = mode
        self._left_view.set_mode(mode)
        self._status_label.setText(f"ROI mode: {mode} (drag rectangle on left view)")

    def _on_rect_update(self, rect: Rect, final: bool) -> None:
        rect = _normalize_rect(rect, self._left_view.image_size())
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

    def _clear_lane(self) -> None:
        self._lane_rect = None
        self._status_label.setText("Lane ROI cleared.")

    def _clear_plate(self) -> None:
        self._plate_rect = None
        self._status_label.setText("Plate ROI cleared.")

    def _save_rois(self) -> None:
        lane_poly = _rect_to_polygon(self._lane_rect)
        plate_poly = _rect_to_polygon(self._plate_rect)
        save_rois(self._roi_path, lane_poly, plate_poly)
        if lane_poly is not None:
            lane_rois = {
                "left": LaneRoi(polygon=lane_poly),
                "right": LaneRoi(polygon=lane_poly),
            }
            save_lane_rois(self._lane_path, lane_rois)
        self._status_label.setText("ROIs saved.")

    def _load_rois(self) -> None:
        rois = load_rois(self._roi_path)
        self._lane_rect = _polygon_to_rect(rois.get("lane"))
        self._plate_rect = _polygon_to_rect(rois.get("plate"))
        if self._lane_rect or self._plate_rect:
            self._status_label.setText("ROIs loaded.")

    def _load_detector_defaults(self) -> None:
        cfg = self._config.detector
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
        self._service.set_detector_config(detector_cfg, mode)
        self._service.set_detection_threading(
            self._detection_threading, self._detection_workers
        )
        self._status_label.setText("Detector settings applied.")

    def _set_ball_type(self, ball_type: str) -> None:
        self._service.set_ball_type(ball_type)

    def _set_batter_height(self, value: float) -> None:
        self._service.set_batter_height_in(value)

    def _set_strike_ratios(self) -> None:
        self._service.set_strike_zone_ratios(
            self._top_ratio.value(),
            self._bottom_ratio.value(),
        )

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

    def _build_health_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Health")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._health_left)
        layout.addWidget(self._health_right)
        layout.addWidget(self._calib_summary)
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
            self._apply_detector_config()

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
        return Path("configs/default.yaml")


def _frame_to_pixmap(
    image: np.ndarray,
    overlays: list[Overlay] | None = None,
    detections: list | None = None,
    lane_detections: list | None = None,
    plate_detections: list | None = None,
    plate_rect: Optional[Rect] = None,
    zone: tuple[int, int] | None = None,
    trail: list[tuple[int, int]] | None = None,
) -> QtGui.QPixmap:
    if image.ndim == 2:
        height, width = image.shape
        qimage = QtGui.QImage(
            image.data,
            width,
            height,
            image.strides[0],
            QtGui.QImage.Format_Grayscale8,
        )
    else:
        height, width, _ = image.shape
        rgb = image[..., ::-1].copy()
        qimage = QtGui.QImage(
            rgb.data,
            width,
            height,
            rgb.strides[0],
            QtGui.QImage.Format_RGB888,
        )
    pixmap = QtGui.QPixmap.fromImage(qimage)
    if overlays or detections or lane_detections or plate_detections or plate_rect or zone or trail:
        painter = QtGui.QPainter(pixmap)
        if overlays:
            for rect, color in overlays:
                painter.setPen(QtGui.QPen(color, 2))
                painter.drawRect(*rect)
        _draw_detections(painter, detections, QtGui.QColor(255, 0, 0))
        _draw_detections(painter, lane_detections, QtGui.QColor(0, 200, 255))
        _draw_detections(painter, plate_detections, QtGui.QColor(255, 180, 0))
        _draw_trail(painter, trail, QtGui.QColor(0, 255, 100))
        if plate_rect:
            _draw_plate_grid(painter, plate_rect, QtGui.QColor(255, 180, 0), zone)
        painter.end()
    return pixmap


def _current_serial(combo: QtWidgets.QComboBox) -> str:
    data = combo.currentData()
    if isinstance(data, str) and data.strip():
        return data.strip()
    return combo.currentText().strip()


def _probe_opencv_indices(max_index: int = 8) -> list[int]:
    indices: list[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()
        if ok:
            indices.append(i)
    return indices


def _probe_uvc_devices() -> list[dict[str, str]]:
    devices = list_uvc_devices()
    usable: list[dict[str, str]] = []
    for device in devices:
        name = device.get("friendly_name", "")
        if not name:
            continue
        cap = cv2.VideoCapture(f"video={name}", cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()
        if ok:
            usable.append(device)
    return usable


class RoiLabel(QtWidgets.QLabel):
    def __init__(self, on_rect_update) -> None:
        super().__init__()
        self._on_rect_update = on_rect_update
        self._mode: Optional[str] = None
        self._start: Optional[QtCore.QPoint] = None
        self._image_size: Optional[tuple[int, int]] = None

    def set_mode(self, mode: Optional[str]) -> None:
        self._mode = mode

    def set_image_size(self, width: int, height: int) -> None:
        self._image_size = (width, height)

    def image_size(self) -> Optional[tuple[int, int]]:
        return self._image_size

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._mode is None or self._image_size is None:
            return
        if event.button() == QtCore.Qt.LeftButton:
            self._start = event.position().toPoint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._start is None or self._image_size is None:
            return
        current = event.position().toPoint()
        start = self._map_point(self._start)
        end = self._map_point(current)
        rect = _points_to_rect(start, end)
        if rect:
            self._on_rect_update(rect, False)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._start is None or self._image_size is None:
            return
        if event.button() == QtCore.Qt.LeftButton:
            end = event.position().toPoint()
            start = self._map_point(self._start)
            end = self._map_point(end)
            rect = _points_to_rect(start, end)
            if rect:
                self._on_rect_update(rect, True)
        self._start = None

    def _map_point(self, point: QtCore.QPoint) -> QtCore.QPoint:
        if self._image_size is None:
            return point
        label_w = max(self.width(), 1)
        label_h = max(self.height(), 1)
        img_w, img_h = self._image_size
        x = int(point.x() * img_w / label_w)
        y = int(point.y() * img_h / label_h)
        return QtCore.QPoint(x, y)


Rect = tuple[int, int, int, int]
Overlay = tuple[Rect, QtGui.QColor]


def _points_to_rect(start: QtCore.QPoint, end: QtCore.QPoint) -> Optional[Rect]:
    x1 = start.x()
    y1 = start.y()
    x2 = end.x()
    y2 = end.y()
    if x1 == x2 or y1 == y2:
        return None
    return (x1, y1, x2, y2)


def _normalize_rect(rect: Rect, image_size: Optional[tuple[int, int]]) -> Optional[Rect]:
    if image_size is None:
        return None
    width, height = image_size
    x1, y1, x2, y2 = rect
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    x1 = max(0, min(x1, width - 1))
    x2 = max(0, min(x2, width - 1))
    y1 = max(0, min(y1, height - 1))
    y2 = max(0, min(y2, height - 1))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return (x1, y1, x2, y2)


def _rect_to_polygon(rect: Optional[Rect]) -> list[tuple[int, int]] | None:
    if rect is None:
        return None
    x1, y1, x2, y2 = rect
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def _polygon_to_rect(polygon: Optional[list[tuple[int, int]]]) -> Optional[Rect]:
    if not polygon:
        return None
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _roi_overlays(
    lane_rect: Optional[Rect],
    plate_rect: Optional[Rect],
    active_rect: Optional[Rect],
) -> list[Overlay]:
    overlays: list[Overlay] = []
    if lane_rect:
        overlays.append((lane_rect, QtGui.QColor(0, 200, 255)))
    if plate_rect:
        overlays.append((plate_rect, QtGui.QColor(255, 180, 0)))
    if active_rect:
        overlays.append((active_rect, QtGui.QColor(0, 255, 0)))
    return overlays


def _draw_detections(
    painter: QtGui.QPainter,
    detections: list | None,
    color: QtGui.QColor,
) -> None:
    if not detections:
        return
    painter.setPen(QtGui.QPen(color, 2))
    for det in detections:
        radius = max(2, int(det.radius_px))
        painter.drawEllipse(
            int(det.u - radius),
            int(det.v - radius),
            int(radius * 2),
            int(radius * 2),
        )


def _draw_plate_grid(
    painter: QtGui.QPainter,
    rect: Rect,
    color: QtGui.QColor,
    zone: tuple[int, int] | None,
) -> None:
    x1, y1, x2, y2 = rect
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return
    if zone is not None:
        row, col = zone
        col_index = max(1, min(3, col)) - 1
        row_index = max(1, min(3, row)) - 1
        cell_w = width / 3.0
        cell_h = height / 3.0
        row_from_top = 2 - row_index
        cell_x1 = x1 + int(cell_w * col_index)
        cell_y1 = y1 + int(cell_h * row_from_top)
        cell_x2 = x1 + int(cell_w * (col_index + 1))
        cell_y2 = y1 + int(cell_h * (row_from_top + 1))
        brush = QtGui.QBrush(QtGui.QColor(255, 180, 0, 60))
        painter.fillRect(
            QtCore.QRect(cell_x1, cell_y1, cell_x2 - cell_x1, cell_y2 - cell_y1),
            brush,
        )
    painter.setPen(QtGui.QPen(color, 1, QtCore.Qt.DashLine))
    for i in range(1, 3):
        x = x1 + int(width * i / 3.0)
        y = y1 + int(height * i / 3.0)
        painter.drawLine(x, y1, x, y2)
        painter.drawLine(x1, y, x2, y)


def _draw_trail(
    painter: QtGui.QPainter,
    trail: list[tuple[int, int]] | None,
    color: QtGui.QColor,
) -> None:
    if not trail or len(trail) < 2:
        return
    painter.setPen(QtGui.QPen(color, 2))
    for i in range(1, len(trail)):
        x1, y1 = trail[i - 1]
        x2, y2 = trail[i]
        painter.drawLine(x1, y1, x2, y2)


class CalibrationGuide(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibration Guide")
        self.resize(640, 480)
        steps = QtWidgets.QTextEdit()
        steps.setReadOnly(True)
        steps.setText(
            "\n".join(
                [
                    "Quick Calibration Steps:",
                    "",
                    "1) Mount & Focus",
                    "   - Lock focus on both lenses at install distance.",
                    "   - Disable auto exposure/gain/WB in the config.",
                    "",
                    "2) Verify Dual Capture",
                    "   - Start capture and confirm both feeds are live.",
                    "   - Check fps and drop rate in the status bar.",
                    "",
                    "3) Calibrate Lane ROI",
                    "   - Click 'Edit Lane ROI' and drag a rectangle around the pitch lane.",
                    "   - Use the area covering roughly 40-60 ft downrange.",
                    "   - Save ROIs.",
                    "",
                    "4) Calibrate Plate ROI",
                    "   - Click 'Edit Plate ROI' and drag around the strike zone + batter box area.",
                    "   - Save ROIs.",
                    "",
                    "5) Stereo Calibration (Optional, but recommended)",
                    "   - Capture checkerboard images for left/right.",
                    "   - Run: python -m calib.quick_calibrate --left ... --right ... --square-mm ... --write",
                    "   - Confirm baseline_ft and focal_length_px updated in config.",
                    "",
                    "6) Test Run/Rise",
                    "   - Observe run/rise in the status bar (plate window).",
                    "",
                    "Tip: Re-run the guide any time you update the rig or lenses.",
                ]
            )
        )
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(steps)
        layout.addWidget(close_button)
        self.setLayout(layout)


class ChecklistDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pre-Record Checklist")
        self.resize(520, 360)
        steps = QtWidgets.QTextEdit()
        steps.setReadOnly(True)
        steps.setText(
            "\n".join(
                [
                    "Pre-Recording Checklist:",
                    "",
                    "- Lenses focused and locked",
                    "- Exposure/gain set to manual",
                    "- FPS stable (>= 58) on both cameras",
                    "- Lane ROI and Plate ROI saved",
                    "- Strike zone settings verified",
                    "- Session name set",
                ]
            )
        )
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(steps)
        layout.addWidget(close_button)
        self.setLayout(layout)


class StartupDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Location and Pitcher")
        self.resize(520, 220)
        self._profile = QtWidgets.QComboBox()
        self._profile.addItems(list_profiles())
        self._pitcher = QtWidgets.QComboBox()
        self._pitcher.setEditable(True)
        self._pitcher.addItems(load_pitchers())
        state = load_state()
        last_pitcher = state.get("last_pitcher")
        if last_pitcher:
            self._pitcher.setCurrentText(last_pitcher)

        form = QtWidgets.QFormLayout()
        form.addRow("Location profile", self._profile)
        form.addRow("Pitcher", self._pitcher)

        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Continue")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def values(self) -> tuple[str, str]:
        return (
            self._profile.currentText().strip(),
            self._pitcher.currentText().strip(),
        )


class SessionSummaryDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        summary,
        on_upload,
        on_save,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Session Summary")
        self.resize(680, 520)
        self._on_upload = on_upload
        self._on_save = on_save

        header = QtWidgets.QLabel(
            f"Session: {summary.session_id} | "
            f"Pitches: {summary.pitch_count} | "
            f"Strikes: {summary.strikes} | "
            f"Balls: {summary.balls}"
        )

        heatmap = QtWidgets.QTableWidget(3, 3)
        heatmap.setHorizontalHeaderLabels(["Inside", "Middle", "Outside"])
        heatmap.setVerticalHeaderLabels(["Top", "Middle", "Bottom"])
        heatmap.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        heatmap.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        for row in range(3):
            for col in range(3):
                value = summary.heatmap[row][col]
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                heatmap.setItem(row, col, item)

        table = QtWidgets.QTableWidget(len(summary.pitches), 7)
        table.setHorizontalHeaderLabels(
            ["Pitch", "Strike", "Zone", "Run (in)", "Rise (in)", "Speed", "Rotation"]
        )
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        for row, pitch in enumerate(summary.pitches):
            zone = "-"
            if pitch.zone_row is not None and pitch.zone_col is not None:
                zone = f"{pitch.zone_row},{pitch.zone_col}"
            values = [
                pitch.pitch_id,
                "Y" if pitch.is_strike else "N",
                zone,
                f"{pitch.run_in:.2f}",
                f"{pitch.rise_in:.2f}",
                f"{pitch.speed_mph:.1f}" if pitch.speed_mph is not None else "-",
                f"{pitch.rotation_rpm:.1f}" if pitch.rotation_rpm is not None else "-",
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col > 0:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                table.setItem(row, col, item)

        export_combo = QtWidgets.QComboBox()
        export_combo.addItem("Session Summary (JSON)", "summary_json")
        export_combo.addItem("Session Summary (CSV)", "summary_csv")
        export_combo.addItem("Training Report (JSON)", "training_report")
        export_combo.addItem("Manifests (ZIP)", "manifests_zip")
        save_button = QtWidgets.QPushButton("Save Session")
        save_button.clicked.connect(lambda: self._on_save(export_combo.currentData()))

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        upload_button = QtWidgets.QPushButton("Upload Session")
        upload_button.clicked.connect(lambda: self._on_upload(summary))

        layout = QtWidgets.QVBoxLayout()
        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(header)
        top_row.addStretch(1)
        export_layout = QtWidgets.QVBoxLayout()
        export_layout.addWidget(save_button)
        export_layout.addWidget(export_combo)
        top_row.addLayout(export_layout)
        layout.addLayout(top_row)
        layout.addWidget(QtWidgets.QLabel("Strike Zone Heatmap"))
        layout.addWidget(heatmap)
        layout.addWidget(QtWidgets.QLabel("Pitch Summary"))
        layout.addWidget(table)
        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(upload_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)
        self.setLayout(layout)


class RecordingSettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        session: str,
        output_dir: str,
        speed_mph: float,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recording Settings")
        self.resize(520, 220)
        self._session = QtWidgets.QLineEdit(session)
        self._output_dir = QtWidgets.QLineEdit(output_dir)
        self._speed = QtWidgets.QDoubleSpinBox()
        self._speed.setMinimum(0.0)
        self._speed.setMaximum(130.0)
        self._speed.setSuffix(" mph")
        self._speed.setValue(speed_mph)
        browse_button = QtWidgets.QPushButton("Browse")
        browse_button.clicked.connect(self._browse)

        form = QtWidgets.QFormLayout()
        output_row = QtWidgets.QHBoxLayout()
        output_row.addWidget(self._output_dir)
        output_row.addWidget(browse_button)
        form.addRow("Session name", self._session)
        form.addRow("Output dir", output_row)
        form.addRow("Measured speed", self._speed)

        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Apply")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _browse(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self._output_dir.setText(path)

    def values(self) -> tuple[str, str, float]:
        return (
            self._session.text().strip(),
            self._output_dir.text().strip(),
            self._speed.value(),
        )


class StrikeZoneSettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        ball_type: str,
        batter_height: float,
        top_ratio: float,
        bottom_ratio: float,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Strike Zone Settings")
        self.resize(420, 200)
        self._ball = QtWidgets.QComboBox()
        self._ball.addItems(["baseball", "softball"])
        self._ball.setCurrentText(ball_type)
        self._height = QtWidgets.QDoubleSpinBox()
        self._height.setMinimum(40.0)
        self._height.setMaximum(96.0)
        self._height.setSuffix(" in")
        self._height.setValue(batter_height)
        self._top = QtWidgets.QDoubleSpinBox()
        self._bottom = QtWidgets.QDoubleSpinBox()
        for ratio in (self._top, self._bottom):
            ratio.setMinimum(0.0)
            ratio.setMaximum(1.0)
            ratio.setSingleStep(0.01)
        self._top.setValue(top_ratio)
        self._bottom.setValue(bottom_ratio)

        form = QtWidgets.QFormLayout()
        form.addRow("Ball type", self._ball)
        form.addRow("Batter height", self._height)
        form.addRow("Top ratio", self._top)
        form.addRow("Bottom ratio", self._bottom)

        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Apply")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def values(self) -> tuple[str, float, float, float]:
        return (
            self._ball.currentText(),
            self._height.value(),
            self._top.value(),
            self._bottom.value(),
        )


class DetectorSettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        mode: str,
        frame_diff: float,
        bg_diff: float,
        bg_alpha: float,
        edge_thresh: float,
        blob_thresh: float,
        min_area: int,
        min_circ: float,
        threading_mode: str,
        worker_count: int,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Detector Settings")
        self.resize(640, 460)
        help_text = QtWidgets.QTextEdit()
        help_text.setReadOnly(True)
        help_text.setText(
            "\n".join(
                [
                    "Detector Tuning Guide:",
                    "",
                    "- Mode: MODE_A uses frame differencing; MODE_B is more robust on busy backgrounds.",
                    "- Frame diff / BG diff: Sensitivity thresholds; lower = more detections, more noise.",
                    "- BG alpha: Background update rate; lower keeps older background longer.",
                    "- Edge thresh: Canny edge strength for MODE_B.",
                    "- Blob thresh: Threshold for blob candidate generation.",
                    "- Min area: Rejects tiny blobs; increase to reduce noise.",
                    "- Min circularity: 0..1; higher rejects non-circular shapes.",
                    "",
                    "Tip: Start with MODE_A and lower thresholds until the cue card is detected.",
                ]
            )
        )
        self._mode = QtWidgets.QComboBox()
        self._mode.addItems([Mode.MODE_A.value, Mode.MODE_B.value])
        self._mode.setCurrentText(mode)
        self._frame_diff = QtWidgets.QDoubleSpinBox()
        self._bg_diff = QtWidgets.QDoubleSpinBox()
        self._bg_alpha = QtWidgets.QDoubleSpinBox()
        self._edge_thresh = QtWidgets.QDoubleSpinBox()
        self._blob_thresh = QtWidgets.QDoubleSpinBox()
        self._min_area = QtWidgets.QSpinBox()
        self._min_circ = QtWidgets.QDoubleSpinBox()
        self._threading = QtWidgets.QComboBox()
        self._threading.addItem("Per-camera threads", "per_camera")
        self._threading.addItem("Worker pool", "worker_pool")
        self._threading.setCurrentIndex(
            0 if threading_mode == "per_camera" else 1
        )
        self._workers = QtWidgets.QSpinBox()
        self._workers.setMinimum(1)
        self._workers.setMaximum(8)
        self._workers.setValue(max(1, int(worker_count)))
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
        self._frame_diff.setValue(frame_diff)
        self._bg_diff.setValue(bg_diff)
        self._bg_alpha.setValue(bg_alpha)
        self._edge_thresh.setValue(edge_thresh)
        self._blob_thresh.setValue(blob_thresh)
        self._min_area.setValue(min_area)
        self._min_circ.setValue(min_circ)

        form = QtWidgets.QFormLayout()
        form.addRow("Mode", self._mode)
        form.addRow("Frame diff", self._frame_diff)
        form.addRow("BG diff", self._bg_diff)
        form.addRow("BG alpha", self._bg_alpha)
        form.addRow("Edge thresh", self._edge_thresh)
        form.addRow("Blob thresh", self._blob_thresh)
        form.addRow("Min area", self._min_area)
        form.addRow("Min circularity", self._min_circ)
        form.addRow("Detection threading", self._threading)
        form.addRow("Worker count (pool)", self._workers)

        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Apply")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(help_text)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def values(self) -> dict:
        return {
            "mode": self._mode.currentText(),
            "frame_diff": self._frame_diff.value(),
            "bg_diff": self._bg_diff.value(),
            "bg_alpha": self._bg_alpha.value(),
            "edge_thresh": self._edge_thresh.value(),
            "blob_thresh": self._blob_thresh.value(),
            "min_area": self._min_area.value(),
            "min_circ": self._min_circ.value(),
            "threading_mode": self._threading.currentData(),
            "worker_count": self._workers.value(),
        }


class QuickCalibrateDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, config_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Calibrate")
        self.resize(520, 240)
        self._config_path = config_path
        self.updated = False
        self.updates: dict | None = None

        self._left_dir = QtWidgets.QLineEdit()
        self._right_dir = QtWidgets.QLineEdit()
        self._pattern = QtWidgets.QLineEdit("9x6")
        self._square_mm = QtWidgets.QDoubleSpinBox()
        self._square_mm.setMinimum(1.0)
        self._square_mm.setMaximum(1000.0)
        self._square_mm.setValue(25.0)
        self._ext = QtWidgets.QLineEdit("*.png")

        left_browse = QtWidgets.QPushButton("Browse")
        right_browse = QtWidgets.QPushButton("Browse")
        left_browse.clicked.connect(lambda: self._browse_dir(self._left_dir))
        right_browse.clicked.connect(lambda: self._browse_dir(self._right_dir))

        form = QtWidgets.QFormLayout()
        left_row = QtWidgets.QHBoxLayout()
        left_row.addWidget(self._left_dir)
        left_row.addWidget(left_browse)
        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self._right_dir)
        right_row.addWidget(right_browse)
        form.addRow("Left images folder", left_row)
        form.addRow("Right images folder", right_row)
        form.addRow("Pattern (cols x rows)", self._pattern)
        form.addRow("Square size (mm)", self._square_mm)
        form.addRow("Image glob", self._ext)

        buttons = QtWidgets.QHBoxLayout()
        run_button = QtWidgets.QPushButton("Run Calibration")
        close_button = QtWidgets.QPushButton("Close")
        run_button.clicked.connect(self._run)
        close_button.clicked.connect(self.reject)
        buttons.addWidget(run_button)
        buttons.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _browse_dir(self, target: QtWidgets.QLineEdit) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            target.setText(path)

    def _run(self) -> None:
        left_dir = Path(self._left_dir.text().strip())
        right_dir = Path(self._right_dir.text().strip())
        pattern = self._pattern.text().strip()
        glob_pattern = self._ext.text().strip() or "*.png"
        if not left_dir.exists() or not right_dir.exists():
            QtWidgets.QMessageBox.warning(self, "Quick Calibrate", "Select both folders.")
            return
        left_paths = sorted(left_dir.glob(glob_pattern))
        right_paths = sorted(right_dir.glob(glob_pattern))
        if not left_paths or not right_paths:
            QtWidgets.QMessageBox.warning(self, "Quick Calibrate", "No images found.")
            return
        try:
            updates = calibrate_and_write(
                left_paths=left_paths,
                right_paths=right_paths,
                pattern=pattern,
                square_mm=self._square_mm.value(),
                config_path=self._config_path,
            )
        except Exception as exc:  # noqa: BLE001 - show calibration errors
            QtWidgets.QMessageBox.critical(self, "Quick Calibrate", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self,
            "Quick Calibrate",
            f"Updated stereo config: {updates}",
        )
        self.updated = True
        self.updates = updates


class PlatePlaneDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, config_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plate Plane Calibrate")
        self.resize(520, 200)
        self._left = QtWidgets.QLineEdit()
        self._right = QtWidgets.QLineEdit()
        left_browse = QtWidgets.QPushButton("Browse")
        right_browse = QtWidgets.QPushButton("Browse")
        left_browse.clicked.connect(lambda: self._browse(self._left))
        right_browse.clicked.connect(lambda: self._browse(self._right))

        form = QtWidgets.QFormLayout()
        left_row = QtWidgets.QHBoxLayout()
        left_row.addWidget(self._left)
        left_row.addWidget(left_browse)
        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self._right)
        right_row.addWidget(right_browse)
        form.addRow("Left image", left_row)
        form.addRow("Right image", right_row)

        buttons = QtWidgets.QHBoxLayout()
        run_button = QtWidgets.QPushButton("Run")
        cancel_button = QtWidgets.QPushButton("Cancel")
        run_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(run_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _browse(self, target: QtWidgets.QLineEdit) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select image",
            str(Path("recordings")),
            "Image Files (*.png *.jpg *.jpeg *.bmp)",
        )
        if path:
            target.setText(path)

    def values(self) -> tuple[str, str]:
        return (self._left.text().strip(), self._right.text().strip())


def main() -> None:
    args = parse_args()
    app = QtWidgets.QApplication([])
    window = MainWindow(backend=args.backend, config_path=args.config)
    window.resize(1280, 720)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
