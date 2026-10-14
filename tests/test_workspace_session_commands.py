"""Session commands stay responsive, retain failures and drain before application exit."""

from pathlib import Path
from threading import Event, get_ident

import pytest
from PySide6 import QtCore, QtWidgets

from app.services.orchestrator.runtime_status import FinalizedSession, RuntimeFailure
from tests.test_workspace_navigation import DisplayPipeline
from ui.workspace.window import WorkspaceWindow

ROOT = Path(__file__).resolve().parents[1]


class ControlledPipeline(DisplayPipeline):
    def __init__(self):
        super().__init__()
        self.entered, self.continue_command = Event(), Event()
        self.continue_command.set()
        self.calls = []
        self.failure = None
        self.summary_error = False

    def _command(self, operation):
        self.calls.append((operation, get_ident()))
        changes = {"pending_operation": operation, "failure": None}
        if operation == "stop_recording":
            changes["recording_phase"] = "finalizing"
        self.set_status(**changes)
        self.entered.set()
        assert self.continue_command.wait(5)
        if self.failure == operation:
            self.set_status(pending_operation=None, failure=RuntimeFailure(operation, "Injected recoverable failure"))
            raise RuntimeError("Injected recoverable failure")

    def start_capture(self, config, left, right, config_path):
        self.capture_inputs = (config, left, right, config_path)
        self._command("start_capture")
        self.set_status(capture_phase="live", recording_phase="idle", pending_operation=None)

    def start_recording(self, *, pitch_id, session_name, mode):
        self._command("start_recording")
        self.set_status(recording_phase="recording", session_id=session_name, pending_operation=None)
        return ""

    def pause_recording(self):
        self._command("pause_recording")
        self.set_status(recording_phase="paused", pending_operation=None)

    def resume_recording(self):
        self._command("resume_recording")
        self.set_status(recording_phase="recording", pending_operation=None)

    def stop_recording(self):
        self._command("stop_recording")
        receipt = FinalizedSession(self.status.session_id, Path.cwd() / "recordings/synthetic")
        self.set_status(recording_phase="completed", session_id=None, pending_operation=None, finalized_session=receipt)

    def stop_capture(self):
        self._command("stop_capture")
        self.set_status(capture_phase="idle", pending_operation=None)

    def get_last_session_summary(self):
        if self.summary_error:
            raise RuntimeError("Summary unavailable")
        return None

    def get_session_summary(self):
        return None


@pytest.fixture
def session_workspace(monkeypatch, qtbot, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "default.yaml"
    config.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    pipeline = ControlledPipeline()
    window = WorkspaceWindow(backend="sim", config_path=config, pipeline=pipeline, background_tasks=False)
    monkeypatch.setattr("ui.coaching.async_session.ask_confirmation", lambda *args, **kwargs: True)

    def cleanup(_widget):
        pipeline.continue_command.set()
        pipeline.release.set()
        window._exit_confirmed = True
        window.close()
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=10000)

    qtbot.addWidget(window, before_close_func=cleanup)
    window._on_validation_complete([], [])
    window.show()
    yield window, pipeline


def ready(window, pipeline, phase="idle"):
    live = window.page("live")
    live._session_name, live._pitcher_name, live._session_prepared = "synthetic", "Example Pitcher", True
    live.notify_preparation_changed()
    pipeline.set_status(capture_phase="live", recording_phase=phase,
                        session_id="synthetic" if phase != "idle" else None)


@pytest.mark.parametrize("action,phase,operation,next_phase", [
    ("record", "idle", "start_recording", "recording"),
    ("pause", "recording", "pause_recording", "paused"),
    ("resume", "paused", "resume_recording", "recording"),
    ("end", "recording", "stop_recording", "completed"),
    ("stop_preview", "idle", "stop_capture", "idle"),
])
def test_blocked_commands_allow_navigation_and_reject_duplicates(session_workspace, qtbot, action, phase, operation, next_phase):
    window, pipeline = session_workspace
    ready(window, pipeline, phase)
    pipeline.continue_command.clear()
    heartbeat = []
    timer = QtCore.QTimer(window)
    timer.timeout.connect(lambda: heartbeat.append(True))
    timer.start(5)
    window._perform_session_action(action)
    assert window.page("live").session_command_busy()
    assert not window._primary.isEnabled()
    assert not window.page("live")._diagnostics_button.isEnabled()
    assert not window.page("live")._detector_trial_button.isEnabled()
    window._perform_session_action(action)
    qtbot.waitUntil(pipeline.entered.is_set)
    assert window.navigate("sessions")
    assert window.navigate("setup")
    assert not window.page("setup")._open.isEnabled()
    qtbot.waitUntil(lambda: len(heartbeat) >= 3)
    assert len(pipeline.calls) == 1 and pipeline.calls[0][0] == operation
    assert pipeline.calls[0][1] != get_ident()
    assert not window.may_install_update()
    if action == "end":
        assert window._status.text() == "Finalizing"
        assert window._primary_action != "review"
        assert pipeline.status.finalized_session is None
    pipeline.continue_command.set()
    qtbot.waitUntil(lambda: not window.page("live").session_command_busy())
    assert pipeline.status.recording_phase == next_phase
    assert window.navigation_context.page == "setup"
    if action == "stop_preview":
        assert pipeline.status.capture_phase == "idle"
        assert not window.page("live").preparation().prepared


@pytest.mark.parametrize("action,phase,operation,retry", [
    ("record", "idle", "start_recording", "Retry Start Recording"),
    ("pause", "recording", "pause_recording", "Retry Pause"),
    ("resume", "paused", "resume_recording", "Retry Resume"),
    ("end", "recording", "stop_recording", "Retry End Session"),
])
def test_failure_preserves_state_and_supported_retry(session_workspace, qtbot, action, phase, operation, retry):
    window, pipeline = session_workspace
    ready(window, pipeline, phase)
    pipeline.failure = operation
    window._perform_session_action(action)
    qtbot.waitUntil(lambda: not window.page("live").session_command_busy())
    assert window._primary.text() == retry and window._primary.isEnabled()
    assert "Injected recoverable failure" in window._detail.text()
    assert pipeline.status.recording_phase == ("finalizing" if action == "end" else phase)
    assert pipeline.status.finalized_session is None
    pipeline.failure = None
    window._primary.click()
    qtbot.waitUntil(lambda: len(pipeline.calls) == 2 and not window.page("live").session_command_busy())
    assert "Error" not in window._status.text()


def test_exit_waits_for_admitted_start_before_pipeline_shutdown(session_workspace, qtbot):
    window, pipeline = session_workspace
    ready(window, pipeline)
    pipeline.continue_command.clear()
    window._primary.click()
    qtbot.waitUntil(pipeline.entered.is_set)
    assert not window.close()
    worker = window.page("live")._session_ctrl.runner._worker
    qtbot.wait(30)
    assert window.isVisible() and worker.isRunning()
    assert pipeline.shutdown_calls == 0
    pipeline.continue_command.set()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert pipeline.shutdown_calls == 1
    assert window.page("live")._session_ctrl.runner._worker is None


def test_summary_failure_after_finalization_is_not_recording_failure(session_workspace, qtbot):
    window, pipeline = session_workspace
    ready(window, pipeline, "recording")
    pipeline.summary_error = True
    window._perform_session_action("end")
    qtbot.waitUntil(lambda: not window.page("live").session_command_busy())
    assert window._status.text() == "Completed"
    assert "summary unavailable" in window._detail.text().lower()
    assert window._primary_action == "review" and window._new_session.isVisible()
    assert pipeline.status.failure is None


def test_preparation_is_explicit_and_does_not_record(session_workspace, monkeypatch, qtbot):
    window, pipeline = session_workspace

    class PreparationDialog(QtWidgets.QDialog):
        def __init__(self, config, parent, **kwargs):
            super().__init__(parent)
            self.session_name, self.pitcher_name = "synthetic", "Example Pitcher"
            self.left_serial, self.right_serial = "left", "right"
            self.batter_height_in, self.ball_type = config.strike_zone.batter_height_in, config.ball.type

        def exec(self):
            assert window.page("live").session_command_busy()
            assert not window._primary.isEnabled()
            return QtWidgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr("ui.coaching.dialogs.SessionStartDialog", PreparationDialog)
    pipeline.continue_command.clear()
    window._primary.click()
    qtbot.waitUntil(pipeline.entered.is_set)
    assert not window.page("live").preparation().prepared
    pipeline.continue_command.set()
    qtbot.waitUntil(lambda: not window.page("live").session_command_busy())
    assert window._status.text() == "Ready" and window._primary.text() == "Start Recording"
    assert "not being recorded" in window._detail.text()
    assert [operation for operation, thread in pipeline.calls] == ["start_capture"]
    assert window.page("live").preparation().prepared


def test_cancel_end_keeps_recording_and_timers(session_workspace, monkeypatch):
    window, pipeline = session_workspace
    ready(window, pipeline, "recording")
    monkeypatch.setattr("ui.coaching.async_session.ask_confirmation", lambda *args, **kwargs: False)
    window._perform_session_action("end")
    assert pipeline.calls == [] and window._status.text() == "Recording"
    assert window.page("live")._preview_timer.isActive()
    assert not window.page("live").session_command_busy()


def test_preparation_dialog_uses_rig_without_camera_discovery(session_workspace, monkeypatch, qtbot):
    from ui.coaching.dialogs import SessionStartDialog

    window, _pipeline = session_workspace

    def unexpected_probe(*args, **kwargs):
        pytest.fail("Workspace preparation must use guided setup instead of discovering cameras")

    monkeypatch.setattr("ui.device_utils.probe_uvc_devices", unexpected_probe)
    monkeypatch.setattr("ui.device_utils.probe_opencv_indices", unexpected_probe)
    monkeypatch.setattr("app.services.rig_profile.RigProfileService.load_active", lambda self: None)
    for backend in ("sim", "uvc", "opencv"):
        dialog = SessionStartDialog(window.page("live")._config, backend=backend, prepare_only=True)
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == "Prepare Session"
        assert not dialog._left_camera_combo.isEnabled()
        assert dialog._left_camera_combo.currentData() == ("sim-left" if backend == "sim" else "")
        dialog.resize(800, 600)
        dialog.show()
        qtbot.wait(5)
        assert dialog.width() == 800 and dialog.height() == 600
        button = dialog.findChild(QtWidgets.QDialogButtonBox).button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        position = button.mapTo(dialog, QtCore.QPoint(0, 0))
        assert dialog.rect().contains(QtCore.QRect(position, button.size()))


def test_analysis_unavailable_does_not_change_recording_state(session_workspace):
    window, pipeline = session_workspace
    ready(window, pipeline, "recording")
    pipeline.get_quality_diagnostics = lambda: {"quality": {"status": "UNAVAILABLE"}}
    window.page("live")._update_quality_health()
    assert window._status.text() == "Recording"
    assert "unavailable" in window.page("live")._quality_indicator.text()
    assert window._primary.text() == "Pause"


def test_command_runner_with_real_simulator_pipeline(monkeypatch, qtbot, tmp_path):
    from dataclasses import replace
    from app.qt_pipeline_service import QtPipelineService
    from configs.settings import load_config
    from ui.coaching.session_commands import PrepareSession, SessionCommandRunner

    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "default.yaml"
    config_path.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    config = load_config(config_path)
    config = replace(config, camera=replace(config.camera, width=320, height=240, fps=30),
                     recording=replace(config.recording, output_dir=tmp_path / "recordings"))
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    pipeline = QtPipelineService(backend="sim", parent=parent)
    runner = SessionCommandRunner(pipeline, parent)
    results, statuses = [], []
    runner.completed.connect(results.append)
    pipeline.runtime_status_changed.connect(statuses.append)
    try:
        prepared = PrepareSession(config, config_path, "sim-left", "sim-right", "synthetic", "Example Pitcher")
        assert runner.submit("prepare", prepared)
        qtbot.waitUntil(lambda: not runner.busy, timeout=20000)
        assert not results[-1].error and pipeline.runtime_status().capture_phase == "live"
        for operation, phase in (("record", "recording"), ("pause", "paused"), ("resume", "recording"), ("end", "completed")):
            assert runner.submit(operation, session_name="synthetic")
            qtbot.waitUntil(lambda: not runner.busy, timeout=20000)
            assert not results[-1].error
            assert pipeline.runtime_status().recording_phase == phase
        assert pipeline.runtime_status().finalized_session.session_dir.is_dir()
        assert any(status.recording_phase == "finalizing" for status in statuses)
        assert runner.submit("stop_preview")
        qtbot.waitUntil(lambda: not runner.busy, timeout=20000)
        assert not results[-1].error and not pipeline.runtime_status().owns_capture
    finally:
        runner.stop_admission()
        qtbot.waitUntil(lambda: not runner.busy, timeout=20000)
        pipeline.shutdown()
