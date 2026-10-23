"""Qt handoff for a supervised persistent focus preview."""

from __future__ import annotations

from PySide6 import QtCore

from app.services.capture.focus_preview import FocusPreviewService
from app.services.setup_workflow import SetupWorkflowService
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureState


class FocusPreviewController(QtCore.QObject):
    """Poll bounded latest frames and retain workflow admission until worker exit."""

    frame_ready = QtCore.Signal(object)
    busy_changed = QtCore.Signal(bool)
    failed = QtCore.Signal(str)

    def __init__(self, workflow: SetupWorkflowService, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.workflow = workflow
        self.service: FocusPreviewService | None = None
        self._seen: dict[str, int] = {}
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll)

    def start(self) -> None:
        """Camera acquisition is explicit and always admitted by the workflow."""
        if self.timer.isActive():
            return
        reserved = False
        try:
            request = self.workflow.build_capture_request(SetupCapturePurpose.FOCUS)
            reserved = True
            self.service = FocusPreviewService()
            self.service.start(request)
        except Exception as exc:  # UI isolation; failed start releases reserved admission
            if reserved:
                self.workflow.release_capture()
            self.failed.emit(str(exc))
            return
        self._seen.clear()
        self.busy_changed.emit(True)
        self.timer.start()

    def stop(self) -> None:
        """Closing remains pending while the supervisor drains the worker."""
        if self.service is not None:
            self.service.stop()

    def poll(self) -> None:
        service = self.service
        if service is None:
            return
        for side, frame in service.latest().items():
            if self._seen.get(side) != frame.frame_index:
                self._seen[side] = frame.frame_index
                self.frame_ready.emit(frame)
        if service.done:
            self.timer.stop()
            self.workflow.release_capture()
            terminal = service.terminal
            if terminal is not None and terminal.state != SetupCaptureState.CANCELLED:
                self.failed.emit(terminal.message)
            self.busy_changed.emit(False)
