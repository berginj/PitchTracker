"""Calibration wizard dialog for guided multi-step calibration workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from PySide6 import QtCore, QtWidgets

from ui.device_utils import current_serial
from ui.dialogs.calibration_wizard_support import (
    CalibrationWizardSupport,
    build_wizard_steps,
)
from ui.themes import (
    apply_standard_layout,
    get_style_manager,
    polish_form_controls,
    show_message_dialog,
    style_status_label,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


class CalibrationWizardDialog(QtWidgets.QDialog):
    """Multi-step wizard dialog for guided calibration workflow."""

    def __init__(self, parent: QtWidgets.QMainWindow) -> None:
        """Initialize calibration wizard dialog.

        Args:
            parent: MainWindow instance (tight coupling required for wizard)
        """
        super().__init__(parent)
        self.setWindowTitle("Calibration & Training Wizard")
        self.resize(900, 700)  # Larger dialog to accommodate camera previews
        self._style_manager = get_style_manager()
        self._parent = cast("MainWindow", parent)
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
        self._support = CalibrationWizardSupport(parent)
        self._steps = build_wizard_steps(self, self._parent)

        self._title = QtWidgets.QLabel()
        self._style_manager.style_label(self._title, "pageTitle")
        self._detail = QtWidgets.QLabel()
        self._detail.setWordWrap(True)
        self._style_manager.style_label(self._detail, "muted")
        self._status = QtWidgets.QLabel("")
        style_status_label(self._status, "info", "Validation pending")
        self._step_area = QtWidgets.QWidget()
        self._step_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(self._step_layout, margins=(0, 0, 0, 0), spacing=16)
        self._step_area.setLayout(self._step_layout)
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self._update_live_status)
        self._status_timer.start(500)

        self._action_button = QtWidgets.QPushButton()
        self._action_button.clicked.connect(self._run_action)
        self._style_manager.style_button(self._action_button, "primary")

        self._back_button = QtWidgets.QPushButton("Back")
        self._skip_button = QtWidgets.QPushButton("Skip Step")
        self._next_button = QtWidgets.QPushButton("Next")
        self._back_button.clicked.connect(self._go_back)
        self._skip_button.clicked.connect(self._skip_step)
        self._next_button.clicked.connect(self._go_next)
        self._style_manager.style_button(self._back_button, "ghost")
        self._style_manager.style_button(self._skip_button, "ghost")
        self._style_manager.style_button(self._next_button, "primary")

        header = QtWidgets.QVBoxLayout()
        apply_standard_layout(header, margins=(0, 0, 0, 0), spacing=8)
        header.addWidget(self._title)
        header.addWidget(self._detail)
        header.addWidget(self._status)

        # Wrap header and step area in a scrollable container
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(scroll_layout)
        scroll_layout.addLayout(header)
        scroll_layout.addWidget(self._step_area)
        scroll_layout.addStretch(1)
        scroll_content.setLayout(scroll_layout)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_content)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addWidget(self._action_button)
        button_row.addStretch(1)
        button_row.addWidget(self._back_button)
        button_row.addWidget(self._skip_button)
        button_row.addWidget(self._next_button)

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(scroll_area, 1)  # Stretch to fill
        layout.addLayout(button_row)
        self.setLayout(layout)
        polish_form_controls(self)

        self._refresh_step()

    def _refresh_step(self) -> None:
        """Refresh UI for current step."""
        step = self._steps[self._index]
        self._title.setText(f"Step {self._index + 1} of {len(self._steps)}: {step['title']}")
        self._detail.setText(step["detail"])
        self._update_validation_status(step)
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

    def _update_validation_status(self, step: dict) -> None:
        """Update the status chip for the current step."""
        validator = step.get("validate")
        if validator is None:
            style_status_label(self._status, "info", "Validation: not required")
            return
        tone = "success" if validator() else "warning"
        style_status_label(self._status, tone, self._validation_text(step))

    def _run_action(self) -> None:
        """Run action for current step."""
        step = self._steps[self._index]
        action = step.get("action")
        if action is None:
            return
        action()
        self._update_validation_status(step)

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
            show_message_dialog(
                self,
                "Validation",
                "Validation failed for this step. Fix the issue or use Skip Step.",
                tone="warning",
            )
            self._update_validation_status(step)
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
        left_combo.currentTextChanged.connect(lambda text: self._parent._left_input.setCurrentText(text))
        right_combo.currentTextChanged.connect(lambda text: self._parent._right_input.setCurrentText(text))
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
        style_status_label(self._target_label, "warning", "Target detected: no")
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

        flip_left_btn.clicked.connect(lambda checked: self._support.toggle_flip("left", checked))
        flip_right_btn.clicked.connect(lambda checked: self._support.toggle_flip("right", checked))

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
        self._baseline_spin.valueChanged.connect(self._baseline_changed)

        # Helper label showing inches
        baseline_inches = self._parent._config.stereo.baseline_ft * 12
        self._baseline_inches_label = QtWidgets.QLabel(f"({baseline_inches:.1f} inches)")
        self._style_manager.style_label(self._baseline_inches_label, "muted")

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
        fiducial_ids = self._parent._calibration_overlay.fiducial_ids
        plate_id = fiducial_ids["plate"]
        rubber_id = fiducial_ids["rubber"]
        self._fiducial_label = QtWidgets.QLabel("Tags detected: 0")
        style_status_label(self._fiducial_label, "warning", "Tags detected: 0")

        # Make error message collapsible
        self._fiducial_error_label = QtWidgets.QLabel("")
        self._fiducial_error_label.setWordWrap(True)
        style_status_label(self._fiducial_error_label, "error", "")
        self._fiducial_error_label.setMaximumHeight(100)  # Limit height

        # Add scroll area for long error messages
        error_scroll = QtWidgets.QScrollArea()
        error_scroll.setWidget(self._fiducial_error_label)
        error_scroll.setWidgetResizable(True)
        error_scroll.setMaximumHeight(100)
        error_scroll.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        error_scroll.setVisible(False)  # Hidden by default
        self._fiducial_error_scroll = error_scroll

        hint = QtWidgets.QLabel(f"Required IDs: plate={plate_id}, rubber={rubber_id} (AprilTag 36h11, 100mm).")
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
        hint = QtWidgets.QLabel("Draw the lane on the left preview, then propose the right lane.")
        hint.setWordWrap(True)
        form = QtWidgets.QFormLayout()
        form.addRow(hint)
        form.addRow("", propose_button)
        widget.setLayout(form)
        return widget

    def _baseline_changed(self, value_ft: float) -> None:
        """Persist a baseline edit and refresh its derived display."""
        self._support.update_baseline(value_ft)
        baseline_inches = value_ft * 12
        if self._baseline_inches_label is not None:
            self._baseline_inches_label.setText(f"({baseline_inches:.1f} inches)")

    def _update_live_status(self) -> None:
        """Update live status indicators (called by timer)."""
        if self._target_label is None:
            pass
        found = self._parent._calibration_overlay.target_found
        if self._target_label is not None:
            style_status_label(
                self._target_label,
                "success" if found else "warning",
                "Target detected: yes" if found else "Target detected: no",
            )
        if self._fiducial_label is not None:
            ids = [det.tag_id for det in self._parent._calibration_overlay.fiducial_detections]
            style_status_label(
                self._fiducial_label,
                "success" if ids else "warning",
                f"Tags detected: {len(ids)} ({ids})",
            )
        if self._fiducial_error_label is not None and self._fiducial_error_scroll is not None:
            error = self._parent._calibration_overlay.fiducial_error
            if error:
                style_status_label(self._fiducial_error_label, "error", error)
                self._fiducial_error_scroll.setVisible(True)
            else:
                self._fiducial_error_label.setText("")
                self._fiducial_error_scroll.setVisible(False)

    def _finalize(self) -> None:
        """Finalize wizard, stop capture, and write log."""
        try:
            self._parent._stop_capture()
        except Exception:
            pass
        self._support.write_log(self._skipped_steps)
        self.accept()


__all__ = ["CalibrationWizardDialog"]
