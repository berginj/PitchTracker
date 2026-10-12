"""Shared presentation and owned operations for the five guided setup stages."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from app.services.capture.setup_capture import SupervisedSetupCaptureService
from app.services.setup_workflow import SetupWorkflowService
from contracts.setup_capture import SetupCapturePurpose
from ui.setup.setup_capture_controller import SetupCaptureOperation
from ui.setup.steps.base_step import BaseStep
from ui.themes import apply_standard_layout, get_style_manager, style_status_label
from ui.tooling_task import ToolingTaskDialog, run_tooling_task


class WorkflowStep(BaseStep):
    configuration_changed = QtCore.Signal()

    def __init__(self, workflow: SetupWorkflowService, title: str):
        super().__init__()
        self.workflow = workflow
        self.title = title
        self.operation: SetupCaptureOperation | None = None
        self._enabled_before_work: dict[QtWidgets.QWidget, bool] = {}
        self.layout_box = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(self.layout_box)
        self.headline = QtWidgets.QLabel(title)
        get_style_manager().style_label(self.headline, "sectionTitle")
        self.layout_box.addWidget(self.headline)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.layout_box.addWidget(self.status)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(100)
        self.details.setMaximumHeight(220)
        self.details.hide()
        self.details_button = QtWidgets.QPushButton("Details")
        self.details_button.clicked.connect(lambda: self.details.setVisible(not self.details.isVisible()))

    def footer(self) -> None:
        self.layout_box.addWidget(self.details_button)
        self.layout_box.addWidget(self.details)
        self.layout_box.addStretch()

    def get_title(self) -> str:
        return self.title

    def get_description(self) -> str:
        return self.title

    def set_busy(self, busy: bool) -> None:
        if busy and not self.is_busy():
            for widget in self.findChildren(QtWidgets.QWidget):
                if isinstance(widget, (QtWidgets.QAbstractButton, QtWidgets.QComboBox,
                                       QtWidgets.QAbstractSpinBox, QtWidgets.QTableWidget)):
                    if isinstance(widget, QtWidgets.QPushButton) and widget.text() == "Cancel":
                        continue
                    self._enabled_before_work[widget] = widget.isEnabled()
                    widget.setEnabled(False)
        elif not busy:
            for widget, enabled in self._enabled_before_work.items():
                widget.setEnabled(enabled)
            self._enabled_before_work.clear()
        super().set_busy(busy)

    def on_enter(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.show_saved()

    def show_saved(self) -> None:
        message = "Saved — needs checks" if self.workflow.state["changed"] else "Saved settings"
        style_status_label(self.status, "info", message)

    def action(self, callback: Callable[[], Any], *, edit: bool = False) -> Any:
        try:
            result = callback()
            self.show_saved()
            if edit:
                self.configuration_changed.emit()
            return result
        except Exception as exc:  # noqa: BLE001 - show actionable service failures
            import logging
            logging.getLogger(__name__).exception("Guided setup action failed")
            style_status_label(self.status, "error", str(exc))
            if edit:
                self.workflow.note_unsaved_failure(str(exc))
            self.set_complete(False)
            return None

    def set_details(self, payload: Any) -> None:
        self.details.setPlainText(json.dumps(payload, indent=2, default=str))

    def capture(self, purpose: SetupCapturePurpose, completed: Callable[[Any], None]) -> None:
        if self.is_busy():
            return
        self.operation = SetupCaptureOperation(
            SupervisedSetupCaptureService(), lambda: self.workflow.build_capture_request(purpose),
            self.workflow.apply_capture_result, self,
        )
        self.operation.busy_changed.connect(self.set_busy)
        self.operation.busy_changed.connect(lambda busy: None if busy else self.workflow.release_capture())
        self.operation.result_ready.connect(completed)
        self.operation.failed.connect(self.capture_failed)
        self.operation.cancelled.connect(lambda _terminal: style_status_label(self.status, "warning", "Capture cancelled"))
        self.operation.start()

    def capture_failed(self, terminal) -> None:
        self.workflow.release_capture()
        style_status_label(self.status, "error", terminal.message)

    def tooling(self, title: str, operation: Callable[[Any], Any]) -> Any:
        self.set_busy(True)
        try:
            return run_tooling_task(self, title, operation)
        finally:
            self.set_busy(False)

    def cancel_pending(self) -> bool:
        if self.operation is not None and self.operation.busy:
            return self.operation.cancel()
        for dialog in self.findChildren(ToolingTaskDialog):
            if dialog.busy:
                dialog.reject()
                return True
        return False

    def force_cancel_pending(self) -> None:
        if self.operation is not None:
            self.operation.force_kill()
        self.cancel_pending()


def display_image(label: QtWidgets.QLabel, image: Any) -> None:
    import cv2
    rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB if image.ndim == 2 else cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    qimage = QtGui.QImage(rgb.data, width, height, int(rgb.strides[0]), QtGui.QImage.Format.Format_RGB888).copy()
    label.setPixmap(QtGui.QPixmap.fromImage(qimage).scaled(
        label.size(), QtCore.Qt.AspectRatioMode.IgnoreAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation,
    ))
