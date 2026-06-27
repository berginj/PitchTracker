"""Step 5: Stereo overlap and feature-match validation.

Renders the :class:`~contracts.setup.StereoOverlapResult` produced by matching
features between a synchronized stereo pair. All verdict formatting lives in
the Qt-free :mod:`ui.setup.overlap_view` view-model; this widget only lays the
formatted rows out, so the validation result stays unit-testable off-screen.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtWidgets

from contracts.setup import StereoOverlapResult
from ui.setup.overlap_view import (
    present_overlap,
    unknown_overlap_result,
)
from ui.setup.quality_report_view import ReportView
from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    apply_standard_layout,
    build_notice,
    get_style_manager,
    style_status_label,
)

# Presenter tones -> StyleManager status-label tones.
_ROW_VALUE_TONES = {"success", "error", "warning", "info"}


class OverlapStep(BaseStep):
    """Step 5: present stereo overlap validation and feature-match findings."""

    def __init__(
        self,
        result_provider: Optional[Callable[[], StereoOverlapResult]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._result_provider = result_provider or unknown_overlap_result
        self._last_result: Optional[StereoOverlapResult] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        self._headline = QtWidgets.QLabel()
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(self._headline, "info", "Stereo overlap")
        layout.addWidget(self._headline)

        layout.addWidget(self._build_metrics_group())
        layout.addWidget(self._build_warnings_group())

        refresh_button = QtWidgets.QPushButton("Re-check Overlap")
        refresh_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        refresh_button.clicked.connect(self.refresh)
        self._style_manager.style_button(refresh_button, "primary")
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
        return "Overlap"

    def get_description(self) -> str:
        return "Validate that both stereo cameras see the same textured scene before rectification."

    def validate(self) -> tuple[bool, str]:
        if self._last_result is None:
            return False, "Run the overlap check first."
        return self._last_result.passed, "" if self._last_result.passed else self._last_result.recommendation

    def on_enter(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Rebuild and render the overlap result from the provider."""
        result = self._result_provider()
        self._last_result = result
        self._render(present_overlap(result))

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
