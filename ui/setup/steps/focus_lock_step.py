"""Step 4: Fixed-focus and exposure lock.

Renders the left/right focus and exposure lock verdicts produced by the stereo
setup backend. All grading and formatting lives in the Qt-free
:mod:`ui.setup.focus_lock_view` view-model; this widget only lays the formatted
rows out, so the verdict logic stays unit-testable off-screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.focus_lock_view import (
    FocusExposureSnapshot,
    present_focus_lock,
    unknown_focus_snapshot,
)
from ui.setup.quality_report_view import ReportView
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


class FocusLockStep(BaseStep):
    """Step 4: present fixed-focus and exposure-lock results."""

    def __init__(
        self,
        snapshot_provider: Optional[Callable[[], FocusExposureSnapshot]] = None,
        operation: Optional["SetupCaptureOperation"] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._snapshot_provider = snapshot_provider or unknown_focus_snapshot
        self._operation = operation
        self._last_view: Optional[ReportView] = None
        self._passed = False
        self._build_ui()
        if self._operation is not None:
            self._operation.busy_changed.connect(self._on_operation_busy)
            self._operation.result_ready.connect(self._apply_snapshot)
            self._operation.failed.connect(self._on_operation_failed)
            self._operation.cancelled.connect(self._on_operation_cancelled)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        self._headline = QtWidgets.QLabel()
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(self._headline, "info", "Focus & exposure")
        layout.addWidget(self._headline)

        layout.addWidget(self._build_metrics_group())
        layout.addWidget(self._build_warnings_group())

        self._refresh_button = QtWidgets.QPushButton("Re-check Focus & Exposure")
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
        return "Focus & Exposure"

    def get_description(self) -> str:
        return "Verify fixed focus and lock exposure on both cameras before calibration."

    def validate(self) -> tuple[bool, str]:
        if self._passed:
            return True, ""
        return False, "Focus and exposure must be locked on both cameras before calibrating."

    def on_enter(self) -> None:
        self.refresh()

    def on_exit(self) -> None:
        self.cancel_pending()
    def refresh(self) -> None:
        """Rebuild and render the focus/exposure snapshot from the provider."""
        if self._operation is not None:
            self._operation.start()
            return
        snapshot = self._snapshot_provider()
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: FocusExposureSnapshot) -> None:
        view = present_focus_lock(snapshot)
        self._passed = all(
            [
                snapshot.focus_left.passed,
                snapshot.focus_right.passed,
                snapshot.exposure_left.passed,
                snapshot.exposure_right.passed,
            ]
        )
        self._last_view = view
        self._render(view)

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
            style_status_label(self._headline, "info", "Capturing focus and exposure evidence…")

    def _on_operation_failed(self, terminal) -> None:
        self._passed = False
        self._last_view = None
        style_status_label(self._headline, "error", terminal.message or "Focus capture failed.")

    def _on_operation_cancelled(self, _terminal) -> None:
        self._passed = False
        self._last_view = None
        style_status_label(self._headline, "warning", "Focus capture was cancelled.")

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
