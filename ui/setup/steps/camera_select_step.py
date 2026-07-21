"""Step 1: Stereo camera selection.

Renders the :class:`~ui.setup.camera_select_view.CameraSelectionSnapshot`
produced by setup-time camera discovery and catalog carry-over. All grading and
formatting lives in the Qt-free :mod:`ui.setup.camera_select_view` view-model;
this widget only lays the formatted rows out, so the gate logic stays
unit-testable off-screen.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.camera_select_view import (
    CameraSelectionSnapshot,
    empty_camera_selection,
    grade_selection,
    present_camera_selection,
)
from ui.setup.quality_report_view import ReportView
from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    GlassButton,
    apply_standard_layout,
    build_notice,
    get_style_manager,
    style_status_label,
)

# Presenter tones -> StyleManager status-label tones.
_ROW_VALUE_TONES = {"success", "error", "warning", "info"}


class CameraSelectStep(BaseStep):
    """Step 1: present stereo camera selection and gate progression."""

    def __init__(
        self,
        snapshot_provider: Optional[Callable[[], CameraSelectionSnapshot]] = None,
        assignment_callback: Optional[Callable[[str, str], None]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._snapshot_provider = snapshot_provider or empty_camera_selection
        self._assignment_callback = assignment_callback
        self._last_snapshot: Optional[CameraSelectionSnapshot] = None
        self._last_grade: Optional[tuple[bool, str]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        self._headline = QtWidgets.QLabel()
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(self._headline, "info", "Camera Selection")
        layout.addWidget(self._headline)

        layout.addWidget(self._build_metrics_group())
        layout.addWidget(self._build_warnings_group())

        self._assignment_group = QtWidgets.QGroupBox("Camera assignment")
        assignment_form = QtWidgets.QFormLayout(self._assignment_group)
        self._left_combo = QtWidgets.QComboBox()
        self._right_combo = QtWidgets.QComboBox()
        assignment_form.addRow("Left camera", self._left_combo)
        assignment_form.addRow("Right camera", self._right_combo)
        apply_button = GlassButton("Apply Assignment", variant="primary")
        apply_button.clicked.connect(self._apply_assignment)
        assignment_form.addRow(apply_button)
        self._assignment_group.setVisible(self._assignment_callback is not None)
        layout.addWidget(self._assignment_group)

        refresh_button = GlassButton("Refresh Cameras", variant="primary")
        refresh_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        layout.addStretch()
        self.setLayout(layout)

    def _build_metrics_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Metrics")
        self._metrics_form = QtWidgets.QFormLayout()
        apply_standard_layout(self._metrics_form, margins=(12, 12, 12, 12), spacing=8)
        group.setLayout(self._metrics_form)
        return group

    def _build_warnings_group(self) -> QtWidgets.QGroupBox:
        self._warnings_group = QtWidgets.QGroupBox("Findings")
        self._warnings_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(self._warnings_layout, margins=(12, 12, 12, 12), spacing=8)
        self._warnings_group.setLayout(self._warnings_layout)
        return self._warnings_group

    def get_title(self) -> str:
        return "Select Cameras"

    def get_description(self) -> str:
        return "Assign distinct left and right global-shutter cameras for stereo tracking."

    def validate(self) -> tuple[bool, str]:
        if self._last_snapshot is None:
            snapshot = self._snapshot_provider()
            self._last_snapshot = snapshot
            self._last_grade = grade_selection(snapshot)
            self.set_complete(self._last_grade[0])
        if self._last_grade is None:
            self._last_grade = grade_selection(self._last_snapshot)
            self.set_complete(self._last_grade[0])
        return self._last_grade

    def on_enter(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Rebuild and render the camera selection snapshot from the provider."""
        snapshot = self._snapshot_provider()
        grade = grade_selection(snapshot)
        self._last_snapshot = snapshot
        self._last_grade = grade
        self.set_complete(grade[0])
        self._populate_assignments(snapshot)
        self._render(present_camera_selection(snapshot))

    def _populate_assignments(self, snapshot: CameraSelectionSnapshot) -> None:
        if self._assignment_callback is None:
            return
        combos = (self._left_combo, self._right_combo)
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            for camera in snapshot.cameras:
                combo.addItem(camera.friendly_name or camera.hardware_id, camera.hardware_id)
            combo.blockSignals(False)
        for index, camera in enumerate(snapshot.cameras):
            if camera.side == "left":
                self._left_combo.setCurrentIndex(index)
            elif camera.side == "right":
                self._right_combo.setCurrentIndex(index)

    def _apply_assignment(self) -> None:
        left_id = str(self._left_combo.currentData() or "")
        right_id = str(self._right_combo.currentData() or "")
        if not left_id or not right_id or left_id == right_id:
            style_status_label(self._headline, "error", "Choose two distinct cameras")
            return
        self._assignment_callback(left_id, right_id)
        self.refresh()

    def _render(self, view: ReportView) -> None:
        style_status_label(self._headline, view.tone, view.headline)

        _clear_form(self._metrics_form)
        for row in view.rows:
            label = QtWidgets.QLabel(row.label)
            self._style_manager.style_label(label, "muted")
            value = QtWidgets.QLabel(row.value)
            if row.tone in _ROW_VALUE_TONES:
                style_status_label(value, row.tone, row.value)
            self._metrics_form.addRow(label, value)

        _clear_layout(self._warnings_layout)
        if view.warnings:
            for warning in view.warnings:
                notice, _ = build_notice(warning, tone="warning")
                self._warnings_layout.addWidget(notice)
        else:
            notice, _ = build_notice("No findings. The camera selection looks good.", tone="success")
            self._warnings_layout.addWidget(notice)


def _clear_form(form: QtWidgets.QFormLayout) -> None:
    while form.rowCount():
        form.removeRow(0)


def _clear_layout(layout: QtWidgets.QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
