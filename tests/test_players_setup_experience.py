"""Consistent roster actions, historical filters and saved setup presentation."""

import json
from unittest.mock import patch

from PySide6 import QtCore

from configs.pitchers import add_pitcher, load_pitchers
from contracts.pitcher import PitcherSelection
from scripts.ux_review_fixtures import SyntheticReviewReader, write_session
from tests import test_workspace_navigation as navigation
from ui.team.team_manager import TeamManager
from ui.workspace.contracts import ReviewSelection

workspace = navigation.workspace


def test_browse_and_use_as_active_are_distinct_commands(workspace, qtbot):
    window, pipeline = workspace
    add_pitcher("Example Pitcher")
    window.navigate("players")
    roster = window.page("players")._roster
    roster._on_pitcher_clicked("Example Pitcher")
    assert pipeline.status.pitcher.active_name is None
    roster._on_select_clicked()
    assert window.navigation_context.page == "sessions"
    assert pipeline.status.pitcher.active_name is None
    window.navigate("players")
    roster._active_btn.click()
    live = window.page("live")
    qtbot.waitUntil(lambda: not live.session_command_busy(), timeout=10000)
    assert pipeline.status.pitcher.active_name == "Example Pitcher"
    assert "Example Pitcher" in window._identity.text()


def test_pending_active_pitcher_is_visible_and_admission_disables_button(workspace):
    window, pipeline = workspace
    add_pitcher("Next")
    window.navigate("players")
    roster = window.page("players")._roster
    roster._on_pitcher_clicked("Next")
    pipeline.set_status(recording_phase="recording", pitcher=PitcherSelection("First", "Next", "pitch_00001"))
    assert "Next pitch: Next" in roster._active_status.text()
    pipeline.set_status(pending_operation="stop_recording", recording_phase="finalizing")
    assert not roster._active_btn.isEnabled()


def test_empty_duplicate_and_keyboard_roster_selection(qtbot, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    roster = TeamManager(browse_only=True)
    qtbot.addWidget(roster)
    assert not roster._select_btn.isEnabled()
    roster._add_pitcher()
    assert "Enter a pitcher name" in roster._feedback.text()
    roster._new_pitcher_edit.setText("Example")
    roster._add_pitcher()
    roster._new_pitcher_edit.setText("example")
    roster._add_pitcher()
    assert "already exists" in roster._feedback.text()
    assert load_pitchers() == ["Example"]
    with qtbot.waitSignal(roster._pitcher_cards[0].clicked):
        qtbot.keyClick(roster._pitcher_cards[0], QtCore.Qt.Key.Key_Return)


def test_player_history_uses_recorded_labels_and_preserves_unknown_artifacts(workspace, tmp_path, monkeypatch):
    monkeypatch.setattr("app.review.review_service.VideoReader", SyntheticReviewReader)
    path = write_session(tmp_path / "recordings")
    first = path / "pitch_00001/manifest.json"
    content = json.loads(first.read_text())
    content["pitcher"] = {"schema_version": "pitcher_attribution.v1", "name": "Example"}
    first.write_text(json.dumps(content))
    original = (path / "pitch_00002/manifest.json").read_bytes()
    window, pipeline = workspace
    pipeline.set_status(capture_phase="live", recording_phase="recording", session_id="active")
    window._on_player_browsed("Example")
    page = window.page("sessions")
    assert page._sessions.count() == 1
    page._open_selected()
    selected = page.review.selection()
    assert selected.session_dir.resolve() == path.resolve()
    assert selected == ReviewSelection(selected.session_dir, "example-bullpen", "pitch_00001", "Example")
    assert len(page.review._service.session.pitches) == 1
    assert (path / "pitch_00002/manifest.json").read_bytes() == original
    page.browse_player("Missing player")
    assert page._sessions.currentData() is None
    assert pipeline.status.recording_phase == "recording"


def test_cancel_pitcher_dialog_does_not_dispatch(workspace, monkeypatch):
    window, pipeline = workspace

    class Cancelled(TeamManager):
        def exec(self):
            return self.DialogCode.Rejected
    monkeypatch.setattr("ui.team.TeamManager", Cancelled)
    with patch.object(pipeline, "change_pitcher") as command:
        window.page("live")._session_ctrl.switch_pitcher()
        command.assert_not_called()


def test_setup_saved_revision_survives_reentry_and_capture_blocks_edits(workspace, tmp_path):
    from tests.test_guided_setup_workflow import _new_workflow
    from ui.setup.guided_steps import build_guided_setup_widgets
    from ui.setup.stereo_setup_window import StereoSetupWindow
    from app.services.setup_workflow.runtime_access import register_capture, release_capture
    import pytest
    directory = tmp_path / "working-setup"
    directory.mkdir()
    workflow = _new_workflow(directory)
    window, pipeline = workspace
    window._setup_factory = lambda: StereoSetupWindow(workflow=workflow, widget_factory=lambda: build_guided_setup_widgets(workflow))
    window.navigate("setup")
    page = window.page("setup")
    page.open_guided_setup()
    wizard = page.wizard
    camera_stage = wizard._steps[0]
    camera_stage.widgets["exposure_us"].setValue(3600)
    camera_stage.widgets["exposure_us"].editingFinished.emit()
    assert str(workflow.generation) in page._saved_status.text()
    assert "Complete" in page._saved_status.text()
    assert window.navigate("players") and window.navigate("setup")
    assert page.wizard is wizard
    assert camera_stage.widgets["exposure_us"].value() == 3600
    with patch.object(workflow, "update_settings", side_effect=OSError("Saved file unavailable")):
        camera_stage.widgets["exposure_us"].setValue(3700)
        camera_stage.widgets["exposure_us"].editingFinished.emit()
    assert "not been saved" in page._saved_status.text()
    root = directory / "calibration/rigs"
    register_capture(18374, root, lambda: None)
    try:
        pipeline.set_status(capture_phase="live")
        assert not wizard.isEnabled()
        with pytest.raises(RuntimeError):
            workflow.update_settings("camera", {"exposure_us": 4000})
    finally:
        release_capture(18374)
