"""Complete desktop lifecycle using real services and synthetic setup/camera inputs."""

import json

from PySide6 import QtCore, QtWidgets

from app.qt_pipeline_service import QtPipelineService
from configs.pitchers import save_pitchers
from exceptions import PitchTrackerError
from tests.test_guided_setup_workflow import _new_workflow, _complete
from ui.coaching.dialogs.session_start import SessionStartDialog
from ui.setup.stereo_setup_window import StereoSetupWindow
from ui.workspace.window import WorkspaceWindow


def test_setup_player_capture_record_pause_finalize_review(qtbot, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    workflow = _new_workflow(tmp_path)
    _complete(workflow, tmp_path)  # Synthetic calibration/check inputs, without physical acquisition.
    save_pitchers(["Example Pitcher"])
    messages = []
    monkeypatch.setattr("ui.setup.stereo_setup_window.show_message_dialog",
                        lambda *args, **kwargs: messages.append(args))
    monkeypatch.setattr("ui.coaching.async_session.ask_confirmation", lambda *args, **kwargs: True)
    # Unexpected dialogs must fail the test instead of silently blocking the test runner.

    def unexpected(*args, **kwargs):
        raise AssertionError(f"Unexpected operator error dialog: {args[1:]}")
    monkeypatch.setattr("ui.coaching.dialogs.session_start.show_message_dialog", unexpected)
    monkeypatch.setattr("ui.review._session_controller.show_message_dialog", unexpected)

    pipeline = QtPipelineService(backend="sim")
    window = WorkspaceWindow(backend="sim", config_path=workflow.config_path, pipeline=pipeline,
                             background_tasks=False, setup_factory=lambda: StereoSetupWindow(workflow=workflow))

    def cleanup(_widget):
        window._exit_confirmed = True
        window.close()
        qtbot.waitUntil(lambda: not window.isVisible() and window._pipeline_closed, timeout=30000)

    qtbot.addWidget(window, before_close_func=cleanup)
    window._on_validation_complete([], [])
    window.resize(800, 600)
    window.show()
    assert window._primary.isVisible()
    live = window.page("live")
    assert not pipeline.is_capturing()

    # Inspect all five setup stages and publish through the actual Finish action.
    assert window.navigate("setup")
    setup = window.page("setup")
    setup._open.click()
    wizard = setup.wizard
    assert wizard is not None
    for _ in range(4):
        wizard._next_button.click()
    assert wizard._machine.current.value == "ready"
    wizard._finish_button.click()
    assert workflow.rigs.load_active() is not None
    assert window.navigation_context.page == "live"
    assert not pipeline.is_capturing()

    assert window.navigate("players")
    roster = window.page("players")._roster
    roster._on_pitcher_clicked("Example Pitcher")
    roster._active_btn.click()
    qtbot.waitUntil(lambda: not live.session_command_busy(), timeout=10000)
    assert pipeline.runtime_status().pitcher.active_name == "Example Pitcher"

    original_exec = QtWidgets.QDialog.exec

    def prepare(dialog):
        def confirm():
            dialog._session_name_input.setText("synthetic-journey")
            dialog._accept()
        QtCore.QTimer.singleShot(0, confirm)
        return original_exec(dialog)
    monkeypatch.setattr(SessionStartDialog, "exec", prepare)
    window._primary.click()
    qtbot.waitUntil(lambda: live.preparation().prepared and not live.session_command_busy(), timeout=30000)
    assert window._status.text() == "Ready"
    assert not pipeline.runtime_status().owns_recording

    def frames_ready():
        try:
            return all(frame is not None for frame in pipeline.get_preview_frames())
        except PitchTrackerError:
            return False  # The public preview contract reports first-frame warm-up explicitly.
    qtbot.waitUntil(frames_ready, timeout=10000)

    def settled(phase):
        return pipeline.runtime_status().recording_phase == phase and not live.session_command_busy()

    window._primary.click()
    qtbot.waitUntil(lambda: settled("recording"), timeout=30000)
    assert window._end.isVisible()
    first_frame = pipeline.get_preview_frames()[0].frame_index
    qtbot.waitUntil(lambda: pipeline.get_preview_frames()[0].frame_index >= first_frame + 3, timeout=10000)
    for page in ("sessions", "players", "setup"):
        assert window.navigate(page)
        assert window._status.text() == "Recording"
        assert pipeline.runtime_status().owns_recording
    assert not setup._open.isEnabled()
    assert not wizard.isEnabled()

    window._primary.click()  # Pause from Setup without changing pages or rig ownership.
    qtbot.waitUntil(lambda: settled("paused"), timeout=10000)
    assert pipeline.is_capturing()
    window._primary.click()
    qtbot.waitUntil(lambda: settled("recording"), timeout=10000)
    window._end.click()
    qtbot.waitUntil(lambda: settled("completed"), timeout=30000)
    completed = pipeline.runtime_status().finalized_session
    assert completed is not None and completed.session_dir.is_dir()
    assert window._status.text() == "Completed"
    assert pipeline.is_capturing()  # Finalization alone does not imply capture shutdown.
    manifests = list(completed.session_dir.glob("*manifest*.json"))
    assert manifests
    for path in manifests:
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)

    window._primary.click()
    assert window.navigation_context.page == "sessions"
    assert window.page("sessions").review.selection().session_dir == completed.session_dir
    window._stop_preview.click()
    qtbot.waitUntil(lambda: not pipeline.is_capturing() and not live.session_command_busy(), timeout=30000)
    assert not pipeline.runtime_status().owns_recording
