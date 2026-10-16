"""Persistent pages, truthful global status, operation admission and owned exit."""

from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from app.services.orchestrator.runtime_status import RuntimeStatus
from ui.workspace.contracts import ReviewSelection, SessionPreparation
from ui.workspace.window import WorkspaceWindow

ROOT = Path(__file__).resolve().parents[1]


class DisplayPipeline(QtCore.QObject):
    pitch_started = QtCore.Signal(int, object)
    pitch_ended = QtCore.Signal(object)
    runtime_status_changed = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.status = RuntimeStatus()
        self.shutdown_calls = 0
        self.release = Event()
        self.release.set()
        self.fail_shutdown = False

    def runtime_status(self):
        return self.status

    def set_status(self, **values):
        self.status = replace(self.status, sequence=self.status.sequence + 1, **values)
        self.runtime_status_changed.emit(self.status)

    def change_pitcher(self, name):
        from contracts.pitcher import PitcherSelection
        self.set_status(pitcher=PitcherSelection(active_name=name))

    def is_capturing(self):
        return self.status.owns_capture

    def set_record_directory(self, path):
        self.record_directory = path

    def get_preview_frames(self):
        return None, None

    def get_recent_pitches(self):
        return []

    def get_session_summary(self):
        return None

    def get_stats(self):
        return {}

    def get_quality_diagnostics(self):
        return {}

    def shutdown(self):
        self.shutdown_calls += 1
        assert self.release.wait(5)
        if self.fail_shutdown:
            raise RuntimeError("Writer drain pending")


@pytest.fixture
def workspace(monkeypatch, qtbot, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "configs/default.yaml"
    config.parent.mkdir()
    config.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    pipeline = DisplayPipeline()
    window = WorkspaceWindow(backend="sim", config_path=config, pipeline=pipeline, background_tasks=False)

    def cleanup(_widget):
        pipeline.fail_shutdown = False
        pipeline.release.set()
        window._exit_confirmed = True
        window.close()
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=10000)

    qtbot.addWidget(window, before_close_func=cleanup)
    window._on_validation_complete([], [])
    window.show()
    yield window, pipeline


def test_navigation_retains_pages_service_timers_and_history(workspace, qtbot):
    window, pipeline = workspace
    live = window.page("live")
    preview_timer = live._preview_timer
    pipeline.set_status(capture_phase="live", recording_phase="recording", session_id="active-session")
    selection = ReviewSelection(Path("recordings/history"), "historical-session", "pitch_00003")
    window._on_review_selection(selection)
    for _ in range(3):
        for page in ("sessions", "players", "setup", "live"):
            assert window.navigate(page)
    assert window.page("live") is live
    assert window.pipeline_service is pipeline
    assert preview_timer is live._preview_timer and preview_timer.isActive()
    assert window.navigation_context.review == selection
    assert "active-session" in window._identity.text()
    assert window._status.text() == "Recording"
    assert pipeline.shutdown_calls == 0
    assert all(not page.isWindow() for page in window._pages.values())
    assert window.page("setup").wizard is None  # Navigation cannot create/edit working rig files.
    assert not (Path.cwd() / "calibration").exists()


@pytest.mark.parametrize("size", [(1366, 768), (1024, 768), (800, 600)])
def test_global_actions_fit_with_real_fonts(workspace, qtbot, size):
    window, _pipeline = workspace
    for filename in ("segoeui.ttf", "segoeuib.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{filename}")
    from ui.themes import get_style_manager
    get_style_manager().apply_to_app(QtWidgets.QApplication.instance())
    for name in ("live", "sessions", "players", "setup"):
        window.navigate(name)
        window.resize(*size)
        qtbot.wait(5)
        assert window.width() <= size[0] and window.height() <= size[1]
        position = window._primary.mapTo(window, QtCore.QPoint(0, 0))
        assert window.rect().contains(QtCore.QRect(position, window._primary.size()))


def test_browsing_player_never_changes_active_pitcher(workspace):
    window, pipeline = workspace
    window._on_preparation_changed(SessionPreparation("Bullpen", "Active Pitcher", True))
    pipeline.set_status(capture_phase="live", recording_phase="paused", session_id="bullpen")
    window._on_player_browsed("Historical Player")
    assert window.navigation_context.browsed_player == "Historical Player"
    assert "Active Pitcher" in window._identity.text()
    assert window._preparation.pitcher_name == "Active Pitcher"
    assert window._status.text() == "Paused"


def test_navigation_allowed_during_runtime_command_and_stale_status_ignored(workspace):
    window, pipeline = workspace
    pipeline.set_status(capture_phase="live", recording_phase="finalizing", pending_operation="stop_recording")
    assert window.navigate("sessions")
    assert not window._primary.isEnabled()
    window._on_runtime_status(RuntimeStatus(sequence=0))
    assert window._runtime.recording_phase == "finalizing"
    assert pipeline.shutdown_calls == 0


def test_setup_navigation_read_only_during_capture(workspace):
    window, pipeline = workspace
    pipeline.set_status(capture_phase="live")
    window.navigate("setup")
    setup = window.page("setup")
    assert not setup._open.isEnabled()
    setup.open_guided_setup()
    assert setup.wizard is None
    assert pipeline.status.capture_phase == "live"


def test_ready_preview_has_an_explicit_stop_action(workspace):
    window, pipeline = workspace
    window._on_preparation_changed(SessionPreparation("Prepared", "Pitcher", True))
    pipeline.set_status(capture_phase="live", recording_phase="idle")
    assert window._stop_preview.isVisible() and window._stop_preview.isEnabled()
    assert window._primary.text() == "Start Recording"


def test_busy_setup_blocks_navigation_and_new_capture(workspace, monkeypatch):
    window, _pipeline = workspace
    window.navigate("setup")
    setup = window.page("setup")
    monkeypatch.setattr(setup, "operation_busy", lambda: True)
    setup.busy_changed.emit(True)
    assert not window._primary.isEnabled()
    assert not window.navigate("live")
    assert window.navigation_context.page == "setup"
    monkeypatch.setattr(setup, "operation_busy", lambda: False)
    assert window.navigate("live")


def test_cancel_exit_keeps_service_and_live_timers(workspace, monkeypatch):
    window, pipeline = workspace
    pipeline.set_status(capture_phase="live", recording_phase="recording", session_id="session")
    monkeypatch.setattr("ui.workspace.window.show_choice_dialog", lambda *_args, **_kwargs: "cancel")
    assert not window.close()
    assert window.isVisible()
    assert window.page("live")._preview_timer.isActive()
    assert not window._exit_confirmed
    assert pipeline.shutdown_calls == 0


def test_exit_retains_shutdown_worker_until_terminal(workspace, monkeypatch, qtbot):
    window, pipeline = workspace
    pipeline.set_status(capture_phase="live", recording_phase="recording", session_id="session")
    pipeline.release.clear()
    monkeypatch.setattr("ui.workspace.window.show_choice_dialog", lambda *_args, **_kwargs: "end")
    assert not window.close()
    worker = window._shutdown_worker
    qtbot.waitUntil(lambda: pipeline.shutdown_calls == 1)
    assert window.isVisible() and worker.isRunning()
    assert not window.close()
    assert window._shutdown_worker is worker and pipeline.shutdown_calls == 1
    pipeline.release.set()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert window._shutdown_worker is None


def test_failed_shutdown_retains_owner_and_requires_retry(workspace, qtbot):
    window, pipeline = workspace
    pipeline.fail_shutdown = True
    assert not window.close()
    qtbot.waitUntil(lambda: window._exit_failure is not None)
    assert window.isVisible() and not window._pipeline_closed
    assert window.pipeline_service is pipeline
    assert window._primary.text() == "Retry Exit"
    pipeline.fail_shutdown = False
    window._primary.click()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert pipeline.shutdown_calls == 2


def test_missing_config_keeps_sessions_reachable(monkeypatch, qtbot, tmp_path):
    monkeypatch.chdir(tmp_path)
    pipeline = DisplayPipeline()
    window = WorkspaceWindow(backend="sim", config_path=tmp_path / "missing.yaml",
                             pipeline=pipeline, background_tasks=False)

    def cleanup(_window):
        window.close()
        qtbot.waitUntil(lambda: not window.isVisible())
    qtbot.addWidget(window, before_close_func=cleanup)
    window._on_validation_complete([], [])
    window.show()
    assert not window.page("live").configuration_available
    assert not window._primary.isEnabled()
    button = next(button for button in window.page("live").findChildren(QtWidgets.QPushButton)
                  if button.text() == "Open Sessions")
    button.click()
    assert window.navigation_context.page == "sessions"
    assert window.pipeline_service is pipeline
    assert pipeline.status.capture_phase == "idle"


@pytest.mark.parametrize("backend", ["sim", "uvc", "opencv"])
def test_workspace_startup_validation_never_acquires_cameras(workspace, qtbot, backend):
    from app.services.tooling import SubprocessToolingService
    from contracts.tooling import EnvironmentValidationResult

    checks = []

    class ValidationService(SubprocessToolingService):
        def validate_environment_with_cancellation(self, cancel_event, *, check_cameras=True):
            checks.append(check_cameras)
            return EnvironmentValidationResult(errors=[], warnings=[])

    window, _pipeline = workspace
    window._backend = backend
    window._validation_service = ValidationService()
    window._start_environment_validation()
    qtbot.waitUntil(lambda: window._validation_thread is None)
    assert checks == [False]


def test_exit_waits_for_validation_cancellation(workspace, qtbot):
    from app.services.tooling import SubprocessToolingService
    from contracts.tooling import EnvironmentValidationResult

    started, release = Event(), Event()
    cancellations = []

    class ValidationService(SubprocessToolingService):
        def validate_environment_with_cancellation(self, cancel_event, *, check_cameras=True):
            cancellations.append(cancel_event)
            started.set()
            assert release.wait(5)
            return EnvironmentValidationResult(errors=[], warnings=[])

    window, pipeline = workspace
    window._validation_service = ValidationService()
    window._start_environment_validation()
    try:
        qtbot.waitUntil(started.is_set)
        worker = window._validation_thread
        assert not window.close()
        qtbot.waitUntil(lambda: window._pipeline_closed)
        assert window.isVisible() and window._validation_thread is worker
        assert cancellations[0].is_set() and pipeline.shutdown_calls == 1
        release.set()
        qtbot.waitUntil(lambda: not window.isVisible())
        assert window._validation_thread is None
    finally:
        release.set()


def test_update_install_admission_preserves_owned_work(workspace):
    window, pipeline = workspace
    assert window.may_install_update()
    window.navigate("sessions")
    assert not window.may_install_update()
    window.navigate("live")
    pipeline.set_status(capture_phase="live")
    assert not window.may_install_update()
    pipeline.set_status(capture_phase="idle", recording_phase="finalizing")
    assert not window.may_install_update()


def test_preparation_config_failure_is_actionable(workspace, monkeypatch):
    window, _pipeline = workspace
    live = window.page("live")

    def failed_refresh():
        raise RuntimeError("Saved settings need correction")

    monkeypatch.setattr(live, "refresh_preparation_config", failed_refresh)
    live.perform_session_action("prepare")
    assert "Saved settings need correction" in window._detail.text()
    assert "Error" in window._status.text()
    assert not live.preparation().prepared
