"""Step 2: Stereo paired preview.

Renders the :class:`~ui.setup.paired_preview_view.PairedPreviewSnapshot`
produced by setup-time left/right preview capture. All grading and formatting
lives in the Qt-free :mod:`ui.setup.paired_preview_view` view-model; this widget
only lays the formatted rows out, so the gate logic stays unit-testable
off-screen.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.paired_preview_view import (
    PairedPreviewSnapshot,
    empty_preview_snapshot,
    grade_preview,
    present_paired_preview,
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


class PairedPreviewStep(BaseStep):
    """Step 2: present the paired stereo preview and gate progression."""

    def __init__(
        self,
        snapshot_provider: Optional[Callable[[], PairedPreviewSnapshot]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._snapshot_provider = snapshot_provider or empty_preview_snapshot
        self._last_grade: tuple[bool, str] = (False, "Refresh the paired preview first.")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        self._headline = QtWidgets.QLabel()
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(self._headline, "info", "Paired preview")
        layout.addWidget(self._headline)

        layout.addWidget(self._build_metrics_group())
        layout.addWidget(self._build_warnings_group())

        refresh_button = GlassButton("Refresh Preview", variant="primary")
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
        return "Paired Preview"

    def get_description(self) -> str:
        return "Confirm a live, time-aligned left/right stream before calibration."

    def validate(self) -> tuple[bool, str]:
        return self._last_grade

    def on_enter(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Rebuild and render the paired-preview snapshot from the provider."""
        snapshot = self._snapshot_provider()
        self._last_grade = grade_preview(snapshot)
        self.set_complete(self._last_grade[0])
        self._render(present_paired_preview(snapshot))

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
            notice, _ = build_notice("No findings. The rig looks good.", tone="success")
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
