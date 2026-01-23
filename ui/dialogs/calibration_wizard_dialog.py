"""Calibration wizard dialog for guided multi-step calibration workflow."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml
from PySide6 import QtCore, QtWidgets

from configs.settings import load_config
from ui.device_utils import current_serial

if TYPE_CHECKING:
    from ui.qt_app import MainWindow


class CalibrationWizardDialog(QtWidgets.QDialog):
    """Multi-step wizard dialog for guided calibration workflow."""

    def __init__(self, parent: "MainWindow") -> None:
        """Initialize calibration wizard dialog.

        Args:
            parent: MainWindow instance (tight coupling required for wizard)
        """
        super().__init__(parent)
        self.setWindowTitle("Calibration & Training Wizard")
        self.resize(900, 700)  # Larger dialog to accommodate camera previews
        self._parent = parent
        self._index = 0
        self._skipped_steps: list[str] = []
        self._device_left: Optional[QtWidgets.QComboBox] = None
        self._device_right: Optional[QtWidgets.QComboBox] = None
        self._target_label: Optional[QtWidgets.QLabel] = None
        self._fiducial_label: Optional[QtWidgets.QLabel] = None
        self._fiducial_error_label: Optional[QtWidgets.QLabel] = None
        self._fiducial_error_scroll: Optional[QtWidgets.QScrollArea] = None
        self._baseline_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._baseline_inches_label: Optional[QtWidgets.QLabel] = None
        self._steps = [
            {
                "title": "Start Capture + Health Check",
                "detail": "Select cameras, refresh devices if needed, start capture, and confirm FPS/drops.",
                "action_label": "Start Capture",
                "action": self._parent._start_capture,
                "widget": self._build_device_selector,
                "validate": self._validate_health,
            },
            {
                "title": "Calibration Target (Checkerboard)",
                "detail": "Place the checkerboard in view. The indicator turns green when detected.",
                "action_label": "Open Guide",
                "action": self._parent._open_calibration_guide,
                "widget": self._build_target_indicator,
                "validate": self._validate_target_detected,
                "target_overlay": True,
            },
            {
                "title": "Fiducials (Plate + Rubber)",
                "detail": "Place AprilTags on the front of the plate and rubber. Both IDs must be detected.",
                "action_label": None,
                "action": None,
                "widget": self._build_fiducial_indicator,
                "validate": self._validate_fiducials,
                "fiducial_overlay": True,
            },
            {
                "title": "Lane ROI",
                "detail": "Draw the lane ROI on the left camera view.",
                "action_label": "Edit Lane ROI",
                "action": lambda: self._parent._set_roi_mode("lane"),
                "widget": self._build_lane_helper,
                "validate": self._validate_lane_roi,
            },
            {
                "title": "Plate ROI",
                "detail": "Draw the plate ROI on the left camera view.",
                "action_label": "Edit Plate ROI",
                "action": lambda: self._parent._set_roi_mode("plate"),
                "validate": self._validate_plate_roi,
            },
            {
                "title": "Quick Calibrate (Checkerboard)",
                "detail": "Run quick stereo calibration from captured checkerboard images.",
                "action_label": "Quick Calibrate",
                "action": self._parent._open_quick_calibrate,
                "validate": self._validate_quick_calibrate,
            },
            {
                "title": "Plate Plane Calibration",
                "detail": "Estimate plate plane Z from a left/right image pair.",
                "action_label": "Plate Plane Calibrate",
                "action": self._parent._open_plate_calibrate,
                "validate": self._validate_plate_plane,
            },
            {
                "title": "Detector Test",
                "detail": "Run the cue card test and confirm detections appear.",
                "action_label": "Cue Card Test",
                "action": self._parent._cue_card_test,
                "validate": self._validate_detector_activity,
            },
            {
                "title": "Ready",
                "detail": "Calibration steps are complete. You can enter the app.",
                "action_label": None,
                "action": None,
                "validate": None,
            },
        ]

        self._title = QtWidgets.QLabel()
        self._title.setStyleSheet("font-weight: bold; font-size: 16px;")
        self._detail = QtWidgets.QLabel()
        self._detail.setWordWrap(True)
        self._status = QtWidgets.QLabel("")
        self._step_area = QtWidgets.QWidget()
        self._step_layout = QtWidgets.QVBoxLayout()
        self._step_layout.setContentsMargins(0, 0, 0, 0)
        self._step_area.setLayout(self._step_layout)
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self._update_live_status)
        self._status_timer.start(500)

        self._action_button = QtWidgets.QPushButton()
        self._action_button.clicked.connect(self._run_action)

        self._back_button = QtWidgets.QPushButton("Back")
        self._skip_button = QtWidgets.QPushButton("Skip Step")
        self._next_button = QtWidgets.QPushButton("Next")
        self._back_button.clicked.connect(self._go_back)
        self._skip_button.clicked.connect(self._skip_step)
        self._next_button.clicked.connect(self._go_next)

        header = QtWidgets.QVBoxLayout()
        header.addWidget(self._title)
        header.addWidget(self._detail)
        header.addWidget(self._status)

        # Wrap header and step area in a scrollable container
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout()
        scroll_layout.addLayout(header)
        scroll_layout.addWidget(self._step_area)
        scroll_layout.addStretch(1)
        scroll_content.setLayout(scroll_layout)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_content)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self._action_button)
        button_row.addStretch(1)
        button_row.addWidget(self._back_button)
        button_row.addWidget(self._skip_button)
        button_row.addWidget(self._next_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(scroll_area, 1)  # Stretch to fill
        layout.addLayout(button_row)
        self.setLayout(layout)

        self._refresh_step()

    def _refresh_step(self) -> None:
        """Refresh UI for current step."""
        step = self._steps[self._index]
        self._title.setText(f"Step {self._index + 1} of {len(self._steps)}: {step['title']}")
        self._detail.setText(step["detail"])
        self._status.setText(self._validation_text(step))
        action_label = step.get("action_label")
        if action_label:
            self._action_button.setText(action_label)
            self._action_button.setEnabled(True)
        else:
            self._action_button.setText("No Action")
            self._action_button.setEnabled(False)
        self._back_button.setEnabled(self._index > 0)
        self._next_button.setText("Finish" if self._index == len(self._steps) - 1 else "Next")
        self._refresh_step_widget(step)
        self._parent._set_target_overlay(bool(step.get("target_overlay", False)))
        self._parent._set_fiducial_overlay(bool(step.get("fiducial_overlay", False)))

    def _refresh_step_widget(self, step: dict) -> None:
        """Refresh step-specific widget.

        Args:
            step: Step configuration dict
        """
        for i in reversed(range(self._step_layout.count())):
            item = self._step_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        builder = step.get("widget")
        self._target_label = None
        self._fiducial_label = None
        self._fiducial_error_label = None
        self._fiducial_error_scroll = None
        if builder is None:
            return
        widget = builder()
        if widget is not None:
            self._step_layout.addWidget(widget)

    def _validation_text(self, step: dict) -> str:
        """Get validation status text for step.

        Args:
            step: Step configuration dict

        Returns:
            Validation status string
        """
        validator = step.get("validate")
        if validator is None:
            return "Validation: not required"
        ok = validator()
        return "Validation: passed" if ok else "Validation: not passed"

    def _run_action(self) -> None:
        """Run action for current step."""
        step = self._steps[self._index]
        action = step.get("action")
        if action is None:
            return
        action()
        self._status.setText(self._validation_text(step))

    def _go_back(self) -> None:
        """Go to previous step."""
        if self._index > 0:
            self._index -= 1
            self._refresh_step()

    def _skip_step(self) -> None:
        """Skip current step and record it."""
        step = self._steps[self._index]
        title = step.get("title")
        if title:
            self._skipped_steps.append(title)
        if self._index >= len(self._steps) - 1:
            self._finalize()
            return
        self._index += 1
        self._refresh_step()

    def _go_next(self) -> None:
        """Validate and go to next step."""
        step = self._steps[self._index]
        validator = step.get("validate")
        if validator is not None and not validator():
            QtWidgets.QMessageBox.warning(
                self,
                "Validation",
                "Validation failed for this step. Fix the issue or use Skip Step.",
            )
            self._status.setText(self._validation_text(step))
            return
        if self._index >= len(self._steps) - 1:
            self._finalize()
            return
        self._index += 1
        self._refresh_step()

    def _validate_devices(self) -> bool:
        """Validate that both cameras are selected.

        Returns:
            True if both cameras have serials
        """
        left = current_serial(self._parent._left_input)
        right = current_serial(self._parent._right_input)
        return bool(left and right)

    def _validate_target_detected(self) -> bool:
        """Validate that calibration target is detected.

        Returns:
            True if target found
        """
        return bool(self._parent._target_found)

    def _validate_fiducials(self) -> bool:
        """Validate that required fiducials are detected.

        Returns:
            True if all required fiducials detected
        """
        if self._parent._fiducial_error:
            return False
        ids = {det.tag_id for det in self._parent._fiducial_detections}
        required = set(self._parent._fiducial_ids.values())
        return required.issubset(ids)

    def _refresh_devices_and_sync(self) -> None:
        """Refresh device list and sync dropdowns."""
        self._parent._refresh_devices()
        self._sync_device_dropdowns()

    def _sync_device_dropdowns(self) -> None:
        """Sync wizard device dropdowns with parent dropdowns."""
        if self._device_left is None or self._device_right is None:
            return
        self._device_left.clear()
        self._device_right.clear()
        for combo, source in (
            (self._device_left, self._parent._left_input),
            (self._device_right, self._parent._right_input),
        ):
            for i in range(source.count()):
                combo.addItem(source.itemText(i), source.itemData(i))
            combo.setEditable(True)
            combo.setCurrentText(source.currentText())

    def _build_device_selector(self) -> Optional[QtWidgets.QWidget]:
        """Build device selection widget.

        Returns:
            Device selector widget
        """
        widget = QtWidgets.QGroupBox("Device Selection")
        left_combo = QtWidgets.QComboBox()
        right_combo = QtWidgets.QComboBox()
        self._device_left = left_combo
        self._device_right = right_combo
        self._sync_device_dropdowns()
        left_combo.currentTextChanged.connect(
            lambda text: self._parent._left_input.setCurrentText(text)
        )
        right_combo.currentTextChanged.connect(
            lambda text: self._parent._right_input.setCurrentText(text)
        )
        form = QtWidgets.QFormLayout()
        form.addRow("Left camera", left_combo)
        form.addRow("Right camera", right_combo)
        refresh_button = QtWidgets.QPushButton("Refresh Devices")
        refresh_button.clicked.connect(self._refresh_devices_and_sync)
        form.addRow("", refresh_button)
        widget.setLayout(form)
        return widget

    def _build_target_indicator(self) -> Optional[QtWidgets.QWidget]:
        """Build target detection indicator widget.

        Returns:
            Target indicator widget
        """
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Target detection status
        detection_group = QtWidgets.QGroupBox("Target Detection")
        self._target_label = QtWidgets.QLabel("Target detected: no")
        detection_layout = QtWidgets.QFormLayout()
        detection_layout.addRow(self._target_label)
        detection_group.setLayout(detection_layout)

        # Camera flip controls
        flip_group = QtWidgets.QGroupBox("Camera Orientation")
        flip_layout = QtWidgets.QHBoxLayout()

        flip_left_btn = QtWidgets.QPushButton("Flip Left 180°")
        flip_right_btn = QtWidgets.QPushButton("Flip Right 180°")

        flip_left_btn.setCheckable(True)
        flip_right_btn.setCheckable(True)

        # Set initial state from config
        flip_left_btn.setChecked(self._parent._config.camera.flip_left)
        flip_right_btn.setChecked(self._parent._config.camera.flip_right)

        flip_left_btn.clicked.connect(lambda checked: self._toggle_flip("left", checked))
        flip_right_btn.clicked.connect(lambda checked: self._toggle_flip("right", checked))

        flip_layout.addWidget(flip_left_btn)
        flip_layout.addWidget(flip_right_btn)
        flip_group.setLayout(flip_layout)

        # Baseline distance setting
        baseline_group = QtWidgets.QGroupBox("Stereo Configuration")
        baseline_layout = QtWidgets.QFormLayout()

        self._baseline_spin = QtWidgets.QDoubleSpinBox()
        self._baseline_spin.setRange(0.5, 10.0)
        self._baseline_spin.setSingleStep(0.125)  # 1.5 inch increments
        self._baseline_spin.setDecimals(3)
        self._baseline_spin.setValue(self._parent._config.stereo.baseline_ft)
        self._baseline_spin.setSuffix(" ft")
        self._baseline_spin.valueChanged.connect(self._update_baseline)

        # Helper label showing inches
        baseline_inches = self._parent._config.stereo.baseline_ft * 12
        self._baseline_inches_label = QtWidgets.QLabel(f"({baseline_inches:.1f} inches)")
        self._baseline_inches_label.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")

        baseline_layout.addRow("Camera Baseline:", self._baseline_spin)
        baseline_layout.addRow("", self._baseline_inches_label)
        baseline_group.setLayout(baseline_layout)

        layout.addWidget(detection_group)
        layout.addWidget(flip_group)
        layout.addWidget(baseline_group)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _build_fiducial_indicator(self) -> Optional[QtWidgets.QWidget]:
        """Build fiducial detection indicator widget.

        Returns:
            Fiducial indicator widget
        """
        widget = QtWidgets.QGroupBox("Fiducial Detection")
        plate_id = self._parent._fiducial_ids["plate"]
        rubber_id = self._parent._fiducial_ids["rubber"]
        self._fiducial_label = QtWidgets.QLabel("Tags detected: 0")

        # Make error message collapsible
        self._fiducial_error_label = QtWidgets.QLabel("")
        self._fiducial_error_label.setWordWrap(True)
        self._fiducial_error_label.setStyleSheet("color: #d32f2f; padding: 5px;")
        self._fiducial_error_label.setMaximumHeight(100)  # Limit height

        # Add scroll area for long error messages
        error_scroll = QtWidgets.QScrollArea()
        error_scroll.setWidget(self._fiducial_error_label)
        error_scroll.setWidgetResizable(True)
        error_scroll.setMaximumHeight(100)
        error_scroll.setFrameShape(QtWidgets.QFrame.StyledPanel)
        error_scroll.setVisible(False)  # Hidden by default
        self._fiducial_error_scroll = error_scroll

        hint = QtWidgets.QLabel(
            f"Required IDs: plate={plate_id}, rubber={rubber_id} (AprilTag 36h11, 100mm)."
        )
        hint.setWordWrap(True)
        form = QtWidgets.QFormLayout()
        form.addRow(hint)
        form.addRow(self._fiducial_label)
        form.addRow(error_scroll)
        widget.setLayout(form)
        return widget

    def _build_lane_helper(self) -> Optional[QtWidgets.QWidget]:
        """Build lane ROI helper widget.

        Returns:
            Lane helper widget
        """
        widget = QtWidgets.QGroupBox("Lane Helper")
        propose_button = QtWidgets.QPushButton("Propose Right Lane")
        propose_button.clicked.connect(self._parent._propose_right_lane)
        hint = QtWidgets.QLabel(
            "Draw the lane on the left preview, then propose the right lane."
        )
        hint.setWordWrap(True)
        form = QtWidgets.QFormLayout()
        form.addRow(hint)
        form.addRow("", propose_button)
        widget.setLayout(form)
        return widget

    def _toggle_flip(self, camera: str, checked: bool) -> None:
        """Toggle camera flip and restart capture.

        Args:
            camera: "left" or "right"
            checked: True to flip 180°, False for normal orientation
        """
        # Update config file
        config_path = self._parent._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("camera", {})

        if camera == "left":
            data["camera"]["flip_left"] = checked
        else:
            data["camera"]["flip_right"] = checked

        config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Reload config
        self._parent._config = load_config(config_path)

        # Restart capture to apply
        if self._parent._capture_running:
            self._parent._stop_capture()
            QtCore.QTimer.singleShot(200, self._parent._start_capture)

        # Show feedback
        orientation = "flipped 180°" if checked else "normal"
        self._parent._status_label.setText(f"{camera.capitalize()} camera {orientation}. Capture restarted.")

    def _update_baseline(self, value_ft: float) -> None:
        """Update baseline distance in config.

        Args:
            value_ft: Baseline distance in feet
        """
        # Update config file
        config_path = self._parent._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("stereo", {})
        data["stereo"]["baseline_ft"] = float(value_ft)
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Reload config
        self._parent._config = load_config(config_path)

        # Update inches label
        baseline_inches = value_ft * 12
        if hasattr(self, "_baseline_inches_label"):
            self._baseline_inches_label.setText(f"({baseline_inches:.1f} inches)")

        # Show feedback
        self._parent._status_label.setText(f"Baseline updated to {value_ft:.3f} ft ({baseline_inches:.1f} inches). Run calibration to refine.")

    def _update_live_status(self) -> None:
        """Update live status indicators (called by timer)."""
        if self._target_label is None:
            pass
        found = self._parent._target_found
        if self._target_label is not None:
            self._target_label.setText("Target detected: yes" if found else "Target detected: no")
        if self._fiducial_label is not None:
            ids = [det.tag_id for det in self._parent._fiducial_detections]
            self._fiducial_label.setText(f"Tags detected: {len(ids)} ({ids})")
        if self._fiducial_error_label is not None and self._fiducial_error_scroll is not None:
            error = self._parent._fiducial_error
            if error:
                self._fiducial_error_label.setText(error)
                self._fiducial_error_scroll.setVisible(True)
            else:
                self._fiducial_error_label.setText("")
                self._fiducial_error_scroll.setVisible(False)

    def _validate_health(self) -> bool:
        """Validate system health.

        Returns:
            True if health check passes
        """
        return self._parent._health_ok()

    def _validate_lane_roi(self) -> bool:
        """Validate that lane ROI is set for both cameras.

        Returns:
            True if both lane ROIs set
        """
        return (
            self._parent._lane_rect is not None
            and self._parent._lane_rect_right is not None
        )

    def _validate_plate_roi(self) -> bool:
        """Validate that plate ROI is set.

        Returns:
            True if plate ROI set
        """
        return self._parent._plate_rect is not None

    def _validate_quick_calibrate(self) -> bool:
        """Validate that stereo calibration is complete.

        Returns:
            True if stereo calibration parameters are set
        """
        config = load_config(self._parent._config_path())
        return (
            config.stereo.cx is not None
            and config.stereo.cy is not None
            and config.stereo.baseline_ft > 0
            and config.stereo.focal_length_px > 0
        )

    def _validate_plate_plane(self) -> bool:
        """Validate that plate plane calibration is complete.

        Returns:
            True if plate plane Z is set and last calibration succeeded
        """
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

    def _validate_detector_activity(self) -> bool:
        """Validate that detector is producing detections.

        Returns:
            True if detector has recent detections
        """
        try:
            detections = self._parent._service.get_latest_detections()
        except Exception:
            return False
        total = sum(len(items) for items in detections.values())
        return total > 0

    def _finalize(self) -> None:
        """Finalize wizard, stop capture, and write log."""
        try:
            self._parent._stop_capture()
        except Exception:
            pass
        self._write_log()
        self.accept()

    def _write_log(self) -> None:
        """Write wizard completion log."""
        log_path = self._parent._config_path().parent / "calibration_wizard_log.json"
        entry = {
            "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "skipped_steps": self._skipped_steps,
        }
        payload = {"runs": []}
        try:
            if log_path.exists():
                payload = json.loads(log_path.read_text())
        except Exception:
            payload = {"runs": []}
        payload.setdefault("runs", [])
        payload["runs"].append(entry)
        try:
            log_path.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass


__all__ = ["CalibrationWizardDialog"]
