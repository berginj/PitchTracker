"""Non-widget behavior for the calibration wizard dialog."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from PySide6 import QtCore

from configs.settings import load_config
from exceptions import CalibrationPersistenceError

if TYPE_CHECKING:
    from ui.qt_app import MainWindow


def build_wizard_steps(dialog: Any, parent: "MainWindow") -> list[dict[str, Any]]:
    """Build the ordered wizard workflow without constructing widgets."""
    return [
        {
            "title": "Start Capture + Health Check",
            "detail": "Select cameras, refresh devices if needed, start capture, and confirm FPS/drops.",
            "action_label": "Start Capture",
            "action": parent._start_capture,
            "widget": dialog._build_device_selector,
            "validate": dialog._support.validate_health,
        },
        {
            "title": "Calibration Target (Checkerboard)",
            "detail": "Place the checkerboard in view. The indicator turns green when detected.",
            "action_label": "Open Guide",
            "action": parent._open_calibration_guide,
            "widget": dialog._build_target_indicator,
            "validate": dialog._support.validate_target_detected,
            "target_overlay": True,
        },
        {
            "title": "Fiducials (Plate + Rubber)",
            "detail": "Place AprilTags on the front of the plate and rubber. Both IDs must be detected.",
            "action_label": None,
            "action": None,
            "widget": dialog._build_fiducial_indicator,
            "validate": dialog._support.validate_fiducials,
            "fiducial_overlay": True,
        },
        {
            "title": "Lane ROI",
            "detail": "Draw the lane ROI on the left camera view.",
            "action_label": "Edit Lane ROI",
            "action": lambda: parent._set_roi_mode("lane"),
            "widget": dialog._build_lane_helper,
            "validate": dialog._support.validate_lane_roi,
        },
        {
            "title": "Plate ROI",
            "detail": "Draw the plate ROI on the left camera view.",
            "action_label": "Edit Plate ROI",
            "action": lambda: parent._set_roi_mode("plate"),
            "validate": dialog._support.validate_plate_roi,
        },
        {
            "title": "Quick Calibrate (Checkerboard)",
            "detail": "Run quick stereo calibration from captured checkerboard images.",
            "action_label": "Quick Calibrate",
            "action": parent._open_quick_calibrate,
            "validate": dialog._support.validate_quick_calibrate,
        },
        {
            "title": "Plate Plane Calibration",
            "detail": "Estimate plate plane Z from a left/right image pair.",
            "action_label": "Plate Plane Calibrate",
            "action": parent._open_plate_calibrate,
            "validate": dialog._support.validate_plate_plane,
        },
        {
            "title": "Detector Test",
            "detail": "Run the cue card test and confirm detections appear.",
            "action_label": "Cue Card Test",
            "action": parent._cue_card_test,
            "validate": dialog._support.validate_detector_activity,
        },
        {
            "title": "Ready",
            "detail": "Calibration steps are complete. You can enter the app.",
            "action_label": None,
            "action": None,
            "validate": None,
        },
    ]


class CalibrationWizardSupport:
    """Own validation and persistence that does not require widget layout."""

    def __init__(self, parent: "MainWindow") -> None:
        self._parent = parent

    def validate_health(self) -> bool:
        return self._parent._health_ok()

    def validate_target_detected(self) -> bool:
        return bool(self._parent._target_found)

    def validate_fiducials(self) -> bool:
        if self._parent._fiducial_error:
            return False
        ids = {det.tag_id for det in self._parent._fiducial_detections}
        return set(self._parent._fiducial_ids.values()).issubset(ids)

    def validate_lane_roi(self) -> bool:
        return self._parent._lane_rect is not None and self._parent._lane_rect_right is not None

    def validate_plate_roi(self) -> bool:
        return self._parent._plate_rect is not None

    def validate_quick_calibrate(self) -> bool:
        config = load_config(self._parent._config_path())
        return (
            config.stereo.cx is not None
            and config.stereo.cy is not None
            and config.stereo.baseline_ft > 0
            and config.stereo.focal_length_px > 0
        )

    def validate_plate_plane(self) -> bool:
        config = load_config(self._parent._config_path())
        plate_z = config.metrics.plate_plane_z_ft
        if plate_z is None or abs(plate_z) < 0.001:
            return False
        log_path = self._parent._config_path().parent / "plate_plane_log.csv"
        if not log_path.exists():
            return True
        try:
            lines = [line.strip() for line in log_path.read_text().splitlines() if line.strip()]
            if len(lines) <= 1:
                return True
            last = lines[-1].split(",")
            return len(last) >= 2 and last[1].strip() == "1"
        except OSError:
            return True

    def validate_detector_activity(self) -> bool:
        try:
            detections = self._parent._service.get_latest_detections()
        except Exception:
            return False
        return sum(len(items) for items in detections.values()) > 0

    def toggle_flip(self, camera: str, checked: bool) -> None:
        config_path = self._parent._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("camera", {})
        data["camera"][f"flip_{camera}"] = checked
        self._write_config(config_path, data)
        self._parent._config = load_config(config_path)
        if self._parent._capture_running:
            self._parent._stop_capture()
            QtCore.QTimer.singleShot(200, self._parent._start_capture)
        orientation = "flipped 180°" if checked else "normal"
        self._parent._status_label.setText(f"{camera.capitalize()} camera {orientation}. Capture restarted.")

    def update_baseline(self, value_ft: float) -> None:
        config_path = self._parent._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("stereo", {})
        data["stereo"]["baseline_ft"] = float(value_ft)
        self._write_config(config_path, data)
        self._parent._config = load_config(config_path)
        baseline_inches = value_ft * 12
        self._parent._status_label.setText(
            f"Baseline updated to {value_ft:.3f} ft ({baseline_inches:.1f} inches). " "Run calibration to refine."
        )

    def write_log(self, skipped_steps: list[str]) -> None:
        log_path = self._parent._config_path().parent / "calibration_wizard_log.json"
        entry = {
            "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "skipped_steps": skipped_steps,
        }
        payload = {"runs": []}
        try:
            if log_path.exists():
                payload = json.loads(log_path.read_text())
        except (OSError, json.JSONDecodeError):
            payload = {"runs": []}
        payload.setdefault("runs", [])
        payload["runs"].append(entry)
        try:
            log_path.write_text(json.dumps(payload, indent=2))
        except OSError:
            pass

    @staticmethod
    def _write_config(config_path: Path, data: dict[str, Any]) -> None:
        try:
            config_path.write_text(yaml.safe_dump(data, sort_keys=False))
        except (OSError, yaml.YAMLError) as exc:
            raise CalibrationPersistenceError(f"Could not persist calibration settings: {config_path}") from exc
