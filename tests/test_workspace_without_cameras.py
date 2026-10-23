"""Real workspace services retain offline access with an unassigned UVC rig."""

from pathlib import Path

import pytest
from PySide6 import QtWidgets

from app.qt_pipeline_service import QtPipelineService
from app.services.setup_workflow import SetupWorkflowService
from configs.pitchers import load_pitchers, save_pitchers
from scripts.ux_review_fixtures import write_session
from ui.coaching.dialogs.session_start import SessionStartDialog
from ui.workspace.contracts import ReviewSelection
from ui.workspace.secondary import WorkspaceHelpDialog
from ui.workspace.window import WorkspaceWindow


@pytest.fixture
def unassigned_workspace(qtbot, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "configs/default.yaml"
    config.parent.mkdir()
    source = Path(__file__).parents[1] / "configs/default.yaml"
    config.write_bytes(source.read_bytes())
    setup = SetupWorkflowService(config, tmp_path / "calibration/rigs", backend="uvc")
    assert setup.state["camera_ids"] == {}

    def forbidden_camera_access(*args, **kwargs):
        raise AssertionError("Offline navigation attempted physical camera access")
    monkeypatch.setattr("capture.device_discovery.list_uvc_devices", forbidden_camera_access)
    monkeypatch.setattr("capture.uvc_backend.UvcCamera.open", forbidden_camera_access)
    pipeline = QtPipelineService(backend="uvc")
    window = WorkspaceWindow(backend="uvc", config_path=config, pipeline=pipeline, background_tasks=False)

    def cleanup(_window):
        window._exit_confirmed = True
        window.close()
        qtbot.waitUntil(lambda: not window.isVisible() and window._pipeline_closed, timeout=30000)
    qtbot.addWidget(window, before_close_func=cleanup)
    window._on_validation_complete([], [])
    window.show()
    yield window, setup


def test_empty_setup_keeps_offline_pages_and_local_help_available(unassigned_workspace, qtbot):
    window, setup = unassigned_workspace
    before = (setup.root / "state.json").read_bytes()
    for page in ("sessions", "players", "setup", "live"):
        assert window.navigate(page)
        assert window.page(page).isVisibleTo(window)
        assert not window.pipeline_service.runtime_status().owns_capture
    assert window.page("setup").wizard is None
    help_dialog = WorkspaceHelpDialog(window)
    qtbot.addWidget(help_dialog)
    help_dialog.show()
    assert help_dialog.isVisible()
    help_dialog.close()
    assert (setup.root / "state.json").read_bytes() == before
    assert setup.rigs.load_active() is None


def test_recorded_metrics_and_roster_work_without_live_assignment(unassigned_workspace, tmp_path):
    window, setup = unassigned_workspace
    save_pitchers(["Example Pitcher"])
    assert load_pitchers() == ["Example Pitcher"]
    session = write_session(tmp_path / "recordings", "offline-example", state="missing-video")
    assert window.navigate("sessions")
    page = window.page("sessions")
    page.open_selection(ReviewSelection(session, pitch_id="pitch_00001"))
    assert page.review.selection().session_dir == session
    assert window.navigation_context.review.pitch_id == "pitch_00001"
    for name in ("players", "setup", "live", "sessions"):
        assert window.navigate(name)
    assert page.review.selection().session_dir == session
    assert not window.pipeline_service.runtime_status().owns_capture
    assert SetupWorkflowService(setup.rigs.config_path, setup.rigs.base_dir, backend="uvc").state["camera_ids"] == {}


def test_unassigned_preparation_explains_capture_prerequisite_and_keeps_cancel(unassigned_workspace, qtbot):
    window, setup = unassigned_workspace
    dialog = SessionStartDialog(setup.config, window, backend="uvc", config_path=setup.config_path,
                                prepare_only=True)
    qtbot.addWidget(dialog)
    buttons = dialog.findChild(QtWidgets.QDialogButtonBox)
    prepare = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    cancel = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    assert not prepare.isEnabled()
    assert "Setup" in prepare.accessibleDescription()
    assert "Sessions, Players and Help" in prepare.accessibleDescription()
    assert cancel.isEnabled()
    dialog.show()
    cancel.click()
    assert not dialog.isVisible()
    assert window.navigate("sessions")
    assert not window.pipeline_service.runtime_status().owns_capture
