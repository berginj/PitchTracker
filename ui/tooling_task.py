"""Modal task runner that keeps Qt responsive and owns workers through exit."""

from __future__ import annotations

from concurrent.futures import CancelledError
import logging
from threading import Event
from typing import Any, Callable

from PySide6 import QtCore, QtGui, QtWidgets
from ui.themes import apply_standard_layout, polish_form_controls, style_progress_bar

logger = logging.getLogger(__name__)


class ToolingThread(QtCore.QThread):
    def __init__(self, operation: Callable[[Event], Any], parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.cancel_event = Event()
        self.operation = operation
        self.result: Any = None
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            if self.cancel_event.is_set():
                raise CancelledError()
            self.result = self.operation(self.cancel_event)
        except CancelledError as exc:
            self.error = exc
        except Exception as exc:  # noqa: BLE001 - return failure to UI after native thread exit
            logger.exception("Desktop tooling operation failed")
            self.error = exc


class ToolingTaskDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, title: str, operation: Callable[[Event], Any]):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)
        self.label = QtWidgets.QLabel(f"{title}…", self)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        progress = QtWidgets.QProgressBar(self)
        progress.setRange(0, 0)
        progress.setAccessibleName(f"{title} progress")
        style_progress_bar(progress)
        layout.addWidget(progress)
        self.cancel_button = QtWidgets.QPushButton("Cancel", self)
        self.cancel_button.setAccessibleName(f"Cancel {title}")
        layout.addWidget(self.cancel_button)
        self.worker = ToolingThread(operation, self)
        self.cancel_button.clicked.connect(self.reject)
        self.worker.finished.connect(self._terminal)
        self._terminal_received = False
        self._parent_close_pending = False
        parent.installEventFilter(self)
        polish_form_controls(self)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self.parent() and event.type() == QtCore.QEvent.Type.Close and self.busy:
            self._parent_close_pending = True
            self.reject()
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    @property
    def busy(self) -> bool:
        return not self._terminal_received

    def reject(self) -> None:
        if self.busy:
            self.worker.cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.label.setText("Cancelling; waiting for the worker to exit…")
            return
        super().reject()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.busy:
            self.reject()
            event.ignore()
        else:
            event.accept()

    def _terminal(self) -> None:
        self.worker.wait()
        self._terminal_received = True
        parent = self.parentWidget()
        if parent is not None:
            parent.removeEventFilter(self)
        self.done(0 if self.worker.cancel_event.is_set() else 1)
        if self._parent_close_pending and parent is not None:
            QtCore.QTimer.singleShot(0, parent.close)


def run_tooling_task(parent: QtWidgets.QWidget, title: str, operation: Callable[[Event], Any]) -> Any:
    dialog = ToolingTaskDialog(parent, title, operation)
    dialog.worker.start()
    dialog.exec()
    if dialog.worker.cancel_event.is_set() or isinstance(dialog.worker.error, CancelledError):
        return None
    if dialog.worker.error is not None:
        raise dialog.worker.error
    return dialog.worker.result
