"""Qt bridge for supervised setup capture jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6 import QtCore

from app.services.capture.setup_capture import SetupCaptureJob, SupervisedSetupCaptureService
from contracts.setup_capture import SetupCaptureRequest, SetupCaptureState, SetupCaptureTerminal


class SetupCaptureOperation(QtCore.QObject):
    """One setup-step operation backed by a disposable worker process.

    The worker monitor emits ``_job_done`` from a Python thread.  Qt queues the
    reducer onto this object's UI thread, preserving ``LiveSetupContext`` as the
    sole owner of mutable setup evidence.
    """

    busy_changed = QtCore.Signal(bool)
    state_changed = QtCore.Signal(object)
    result_ready = QtCore.Signal(object)
    failed = QtCore.Signal(object)
    cancelled = QtCore.Signal(object)
    _job_done = QtCore.Signal(object)

    def __init__(
        self,
        service: SupervisedSetupCaptureService,
        request_factory: Callable[[], SetupCaptureRequest],
        result_reducer: Callable[[Any], Any],
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._request_factory = request_factory
        self._result_reducer = result_reducer
        self._job: SetupCaptureJob | None = None
        self._busy = False
        self._job_done.connect(self._finish_on_ui_thread)

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def active_job(self) -> SetupCaptureJob | None:
        return self._job

    def start(self) -> bool:
        if self._busy:
            return False
        try:
            request = self._request_factory()
            job = self._service.submit(request)
        except Exception as exc:  # noqa: BLE001 - present actionable setup error
            terminal = SetupCaptureTerminal(
                correlation_id="setup_not_started",
                state=SetupCaptureState.FAILED,
                message=str(exc),
            )
            self.failed.emit(terminal)
            return False
        self._job = job
        self._set_busy(True)
        self.state_changed.emit(job.state)
        job.add_done_callback(lambda finished: self._job_done.emit(finished))
        return True

    def cancel(self) -> bool:
        job = self._job
        if job is None or not self._busy:
            return False
        changed = job.cancel()
        if changed:
            self.state_changed.emit(SetupCaptureState.CANCELLING)
        return changed

    def force_kill(self) -> None:
        job = self._job
        if job is not None and self._busy:
            job.force_kill()

    def wait(self, timeout_seconds: float) -> bool:
        job = self._job
        return True if job is None else job.wait(timeout_seconds)

    @QtCore.Slot(object)
    def _finish_on_ui_thread(self, job: SetupCaptureJob) -> None:
        if job is not self._job:
            # A late callback must never complete a newer operation.
            job.cleanup_artifacts()
            return
        terminal = job.terminal
        try:
            if terminal is None:
                self.failed.emit(
                    SetupCaptureTerminal(
                        job.request.correlation_id,
                        SetupCaptureState.FAILED,
                        message="setup capture ended without terminal state",
                    )
                )
            elif terminal.state == SetupCaptureState.SUCCEEDED and job.result is not None:
                try:
                    reduced = self._result_reducer(job.result)
                except Exception as exc:  # noqa: BLE001 - stale/malformed results fail closed
                    self.failed.emit(
                        SetupCaptureTerminal(
                            job.request.correlation_id,
                            SetupCaptureState.FAILED,
                            message=str(exc),
                        )
                    )
                else:
                    self.result_ready.emit(reduced)
            elif terminal.state == SetupCaptureState.CANCELLED:
                self.cancelled.emit(terminal)
            else:
                self.failed.emit(terminal)
        finally:
            job.cleanup_artifacts()
            self._job = None
            self._set_busy(False)
            if terminal is not None:
                self.state_changed.emit(terminal.state)

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)


__all__ = ["SetupCaptureOperation"]
