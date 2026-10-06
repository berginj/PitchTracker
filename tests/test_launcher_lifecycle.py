"""Launcher shutdown must retain workers until their terminal signal."""

from threading import Event

import pytest

from contracts.tooling import EnvironmentValidationResult
from app.services.tooling import SubprocessToolingService
import launcher
from launcher_threads import StartupValidationThread


@pytest.mark.parametrize("backend", ["sim", "uvc", "opencv"])
def test_startup_validation_respects_backend_camera_intent(monkeypatch, qtbot, backend) -> None:
    requests = []

    class RecordingService(SubprocessToolingService):
        def _run_task(self, task, payload, timeout_seconds=120, *, cancel_event=None):
            requests.append((task, payload, {"cancel_event": cancel_event}))
            return {"errors": [], "warnings": []}

    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)
    window = launcher.LauncherWindow(backend=backend, validation_service=RecordingService())
    qtbot.addWidget(window)
    window._start_environment_validation()
    qtbot.waitUntil(lambda: window._validation_thread is None)
    assert window._validation_state == "completed"
    assert len(requests) == 1
    expected_payload = {"check_cameras": False} if backend == "sim" else {}
    assert requests[0][0:2] == ("validate_environment", expected_payload)
    assert isinstance(requests[0][2]["cancel_event"], Event)
    assert window.close()


def test_repeated_close_waits_for_validation_terminal_state(monkeypatch, qtbot) -> None:
    started, release = Event(), Event()
    cancellation_tokens = []

    class BlockedService(SubprocessToolingService):
        def validate_environment_with_cancellation(self, cancel_event, *, check_cameras=True):
            cancellation_tokens.append(cancel_event)
            started.set()
            release.wait(5)
            return EnvironmentValidationResult(errors=[], warnings=[])

    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)
    window = launcher.LauncherWindow(validation_service=BlockedService())
    qtbot.addWidget(window)
    window.show()
    window._start_environment_validation()
    worker = window._validation_thread
    try:
        qtbot.waitUntil(started.is_set)
        assert window.close() is False
        assert window.close() is False
        assert window.isVisible()
        assert cancellation_tokens[0].is_set()
        assert worker.isRunning()
        assert window._validation_thread is worker
        release.set()
        qtbot.waitUntil(lambda: window._validation_thread is None)
        assert not window.isVisible()
        assert window._validation_state == "pending"  # closing suppresses stale results
    finally:
        release.set()
        if window._validation_thread is worker:
            worker.wait(5000)


def test_result_does_not_release_worker_until_finished(monkeypatch, qtbot) -> None:
    release = Event()

    class PausedResultThread(StartupValidationThread):
        def run(self):
            self.validation_complete.emit([], ["test warning"])
            release.wait(5)

    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)
    monkeypatch.setattr(launcher, "StartupValidationThread", PausedResultThread)
    window = launcher.LauncherWindow()
    qtbot.addWidget(window)
    window._start_environment_validation()
    worker = window._validation_thread
    try:
        qtbot.waitUntil(lambda: window._validation_state == "completed")
        assert window._setup_button.isEnabled()
        assert window._validation_thread is worker
        assert worker.isRunning()
        release.set()
        qtbot.waitUntil(lambda: window._validation_thread is None)
        assert window.close()
    finally:
        release.set()
        if window._validation_thread is worker:
            worker.wait(5000)


def test_close_before_scheduled_validation_prevents_start(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)
    window = launcher.LauncherWindow()
    qtbot.addWidget(window)
    assert window.close()
    window._start_environment_validation()
    assert window._validation_thread is None


def test_validation_worker_retains_legacy_injected_service(qtbot) -> None:
    class LegacyService:
        def validate_environment(self):
            return EnvironmentValidationResult(errors=[], warnings=["legacy"])

    worker = StartupValidationThread(LegacyService())
    with qtbot.waitSignal(worker.validation_complete) as signal:
        worker.start()
    assert worker.wait(5000)
    assert signal.args == [[], ["legacy"]]
