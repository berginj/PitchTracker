"""Step 6: Targetless coarse rectification.

Renders the durable :class:`~contracts.setup.CoarseRectificationResult` produced
by targetless coarse rectification. All verdict and formatting logic lives in
the Qt-free :mod:`ui.setup.rectify_view` view-model; this widget only lays the
formatted rows out, so the verdict logic stays unit-testable off-screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from PySide6 import QtCore, QtWidgets

from contracts.setup import CoarseRectificationResult
from ui.setup.quality_report_view import ReportView
from ui.setup.rectify_view import (
    present_rectification,
    unknown_rectification_result,
)
from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    apply_standard_layout,
    build_notice,
    get_style_manager,
    style_status_label,
)

if TYPE_CHECKING:
    from ui.setup.setup_capture_controller import SetupCaptureOperation

# Presenter tones -> StyleManager status-label tones.
_ROW_VALUE_TONES = {"success", "error", "warning", "info"}


class RectifyStep(BaseStep):
    """Step 6: present targetless coarse rectification and final verdict."""

    def __init__(
        self,
        result_provider: Optional[Callable[[], CoarseRectificationResult]] = None,
        operation: Optional["SetupCaptureOperation"] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._result_provider = result_provider or unknown_rectification_result
        self._operation = operation
        self._last_result: Optional[CoarseRectificationResult] = None
        self._build_ui()
        if self._operation is not None:
            self._operation.busy_changed.connect(self._on_operation_busy)
            self._operation.result_ready.connect(self._apply_result)
            self._operation.failed.connect(self._on_operation_failed)
            self._operation.cancelled.connect(self._on_operation_cancelled)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        self._headline = QtWidgets.QLabel()
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(self._headline, "info", "Coarse rectification")
        layout.addWidget(self._headline)

        layout.addWidget(self._build_metrics_group())
        layout.addWidget(self._build_warnings_group())

        self._refresh_button = QtWidgets.QPushButton("Run Coarse Rectification")
        self._refresh_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._refresh_button.clicked.connect(self.refresh)
        self._style_manager.style_button(self._refresh_button, "primary")
        layout.addWidget(self._refresh_button)
        self._cancel_button = QtWidgets.QPushButton("Cancel Capture")
        self._cancel_button.clicked.connect(self.cancel_pending)
        self._style_manager.style_button(self._cancel_button, "ghost")
        self._cancel_button.hide()
        layout.addWidget(self._cancel_button)

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
        return "Rectification"

    def get_description(self) -> str:
        return "Run targetless coarse rectification and review epipolar alignment."

    def validate(self) -> tuple[bool, str]:
        if self._last_result is None:
            return False, "Run coarse rectification first."
        return self._last_result.passed, "" if self._last_result.passed else self._last_result.recommendation

    def on_enter(self) -> None:
        self.refresh()

    def on_exit(self) -> None:
        self.cancel_pending()

    def refresh(self) -> None:
        """Rebuild and render the report from the provider."""
        if self._operation is not None:
            self._operation.start()
            return
        result = self._result_provider()
        self._apply_result(result)

    def _apply_result(self, result: CoarseRectificationResult) -> None:
        self._last_result = result
        self._render(present_rectification(result))

    def cancel_pending(self) -> bool:
        return False if self._operation is None else self._operation.cancel()

    def force_cancel_pending(self) -> None:
        if self._operation is not None:
            self._operation.force_kill()

    def _on_operation_busy(self, busy: bool) -> None:
        self.set_busy(busy)
        self._refresh_button.setEnabled(not busy)
        self._cancel_button.setVisible(busy)
        if busy:
            style_status_label(self._headline, "info", "Capturing rectification evidence…")

    def _on_operation_failed(self, terminal) -> None:
        self._last_result = None
        style_status_label(self._headline, "error", terminal.message or "Rectification capture failed.")

    def _on_operation_cancelled(self, _terminal) -> None:
        self._last_result = None
        style_status_label(self._headline, "warning", "Rectification capture was cancelled.")

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


__all__ = ["RectifyStep"]
