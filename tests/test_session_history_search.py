"""Session discovery stays separate from loaded review and runtime ownership."""

import json
from unittest.mock import patch

import pytest
from PySide6 import QtCore

from scripts.ux_review_fixtures import SyntheticReviewReader, write_session
from tests import test_workspace_navigation as navigation
from ui.workspace.contracts import ReviewSelection

workspace = navigation.workspace


@pytest.fixture
def history(workspace, tmp_path, monkeypatch):
    monkeypatch.setattr("app.review.review_service.VideoReader", SyntheticReviewReader)
    paths = [write_session(tmp_path / "recordings", name) for name in (
        "2026-10-28-bullpen", "2026-10-27-location-drills", "2026-10-26-bullpen",
    )]
    window, pipeline = workspace
    assert window.navigate("sessions")
    return window, pipeline, window.page("sessions"), paths


def test_search_filters_names_without_rescanning_or_loading(history):
    _window, _pipeline, page, paths = history
    page.open_selection(ReviewSelection(paths[1], pitch_id="pitch_00002"))
    selected = page.review.selection()
    with patch.object(page.review, "available_sessions") as scan, patch.object(page.review, "open_session") as load:
        page._search.setText("  BuLLPEN  ")
        assert [page._sessions.itemData(i).resolve() for i in range(page._sessions.count())] == [paths[0], paths[2]]
        assert page._history_status.text() == "2 of 3 completed sessions"
        scan.assert_not_called()
        load.assert_not_called()
    assert page.review.selection() == selected
    assert "2026-10-27-location-drills" in page._selection_label.text()
    assert page._review_button.isEnabled()


def test_no_match_explains_recovery_and_clear_restores_selection(history, qtbot):
    _window, _pipeline, page, paths = history
    page._sessions.setCurrentIndex(1)
    page._search.setText("<missing>")
    assert page._sessions.currentData() is None
    assert not page._review_button.isEnabled()
    assert not page._sessions.isEnabled()
    assert "Clear search" in page._history_status.text()
    assert "<missing>" in page._history_status.text()
    assert page._history_status.textFormat() == QtCore.Qt.TextFormat.PlainText
    qtbot.mouseClick(page._clear_search, QtCore.Qt.MouseButton.LeftButton)
    assert page._sessions.currentData().resolve() == paths[1]
    assert page._review_button.isEnabled()
    assert not page._clear_search.isEnabled()


def test_enter_reviews_matching_session_and_preserves_recording(history, qtbot, tmp_path):
    window, pipeline, page, paths = history
    pipeline.set_status(capture_phase="live", recording_phase="recording", session_id="active",
                        active_session_dir=tmp_path / "recordings/active")
    with patch.object(page.review._service, "run_detection_on_current_frame") as detect:
        page._search.setFocus()
        qtbot.keyClicks(page._search, "location")
        qtbot.keyClick(page._search, QtCore.Qt.Key.Key_Return)
        assert page.review.selection().session_dir.resolve() == paths[1].resolve()
        assert window.navigation_context.review == page.review.selection()
        detect.assert_not_called()
    assert pipeline.status.recording_phase == "recording"
    assert pipeline.shutdown_calls == 0
    assert "Active: active" in window._identity.text()


def test_refresh_retains_query_and_selected_result(history, tmp_path):
    _window, _pipeline, page, paths = history
    page._search.setText("bullpen")
    page._sessions.setCurrentIndex(1)
    new = write_session(tmp_path / "recordings", "2026-10-29-bullpen")
    page.refresh()
    assert page._search.text() == "bullpen"
    assert page._sessions.currentData().resolve() == paths[2]
    assert page._sessions.itemData(0).resolve() == new
    assert page._history_status.text() == "3 of 4 completed sessions"
    assert page.review.selection().session_dir is None


def test_direct_handoff_clears_conflicting_search_and_selects_new_session(history, tmp_path):
    _window, _pipeline, page, paths = history
    page._search.setText("location")
    new = write_session(tmp_path / "recordings", "2026-10-29-bullpen")
    page.open_selection(ReviewSelection(new, pitch_id="pitch_00002"))
    assert page._search.text() == ""
    assert page._sessions.currentData().resolve() == new
    assert page.review.selection().pitch_id == "pitch_00002"
    assert "2026-10-29-bullpen" in page._selection_label.text()
    assert page._sessions.count() == len(paths) + 1


def test_failed_handoff_preserves_search_player_filter_and_picker(history, tmp_path):
    _window, _pipeline, page, paths = history
    page.open_selection(ReviewSelection(paths[1], pitch_id="pitch_00002"))
    selection = page.review.selection()
    page._search.setText("location")
    with patch("ui.review._session_controller.show_message_dialog"):
        page.open_selection(ReviewSelection(tmp_path / "missing", pitcher_name="Other Player"))
    assert page.review.selection() == selection
    assert page._player_filter is None
    assert page._search.text() == "location"
    assert page._sessions.currentData().resolve() == paths[1]
    assert not page._clear_player.isVisible()
    assert "try again" in page._selection_label.text()


def test_search_intersects_recorded_player_filter_without_changing_artifacts(history):
    _window, pipeline, page, paths = history
    manifest = paths[1] / "pitch_00001/manifest.json"
    payload = json.loads(manifest.read_text())
    payload["pitcher_name"] = "Example Player"
    manifest.write_text(json.dumps(payload))
    original = manifest.read_bytes()
    page.browse_player("Example Player")
    page._search.setText("bullpen")
    assert page._sessions.currentData() is None
    page._search.setText("LOCATION")
    assert page._sessions.currentData().resolve() == paths[1]
    assert "Recorded player: Example Player" in page._history_status.text()
    assert manifest.read_bytes() == original
    assert pipeline.status.pitcher.active_name is None


def test_history_read_failure_keeps_loaded_review_and_recovers_on_refresh(history, caplog):
    _window, _pipeline, page, paths = history
    page.open_selection(ReviewSelection(paths[1], pitch_id="pitch_00002"))
    selected = page.review.selection()
    page._search.setText("location")
    with patch.object(page.review, "available_sessions", side_effect=PermissionError("Folder is unavailable")):
        page.refresh()
    assert not page._review_button.isEnabled()
    assert "history is unavailable" in page._history_status.text()
    assert "Could not refresh local session history" in caplog.text
    page._search.setText("bullpen")
    assert "history is unavailable" in page._history_status.text()
    assert page.review.selection() == selected
    page.refresh()
    assert page._review_button.isEnabled()
    assert page._history_status.text() == "2 of 3 completed sessions"
    assert page.review.selection() == selected


def test_runtime_path_changes_remove_active_results_and_restore_completed_history(history):
    _window, pipeline, page, paths = history
    page._search.setText("2026-10-28")
    pipeline.set_status(capture_phase="live", recording_phase="recording", active_session_dir=paths[0])
    assert page._sessions.currentData() is None
    assert not page._review_button.isEnabled()
    pipeline.set_status(recording_phase="finalizing")
    assert not page._review_button.isEnabled()
    pipeline.set_status(recording_phase="completed", active_session_dir=None)
    assert page._sessions.currentData().resolve() == paths[0]
    assert page._search.text() == "2026-10-28"
    assert page._review_button.isEnabled()
    assert page.review.selection().session_dir is None


@pytest.mark.parametrize("size", [(1366, 768), (1024, 768), (800, 600)])
def test_search_and_actions_remain_reachable_at_supported_viewports(history, qtbot, size):
    window, _pipeline, page, _paths = history
    window.resize(*size)
    qtbot.wait(20)
    assert (window.width(), window.height()) == size
    for widget in (page._search, page._clear_search, page._sessions, page._review_button, window._primary):
        rect = QtCore.QRect(widget.mapTo(window, QtCore.QPoint()), widget.size())
        assert window.rect().contains(rect)
        assert widget.isVisibleTo(window)
    assert page._search.accessibleName()
    assert page._clear_search.accessibleName()


def test_empty_history_disables_review_and_keeps_local_open_available(workspace, qtbot):
    window, _pipeline = workspace
    window.navigate("sessions")
    page = window.page("sessions")
    assert not page._review_button.isEnabled()
    assert "Open Local" in page._history_status.text()
    page._search.setFocus()
    with patch.object(page.review, "open_session") as load:
        qtbot.keyClick(page._search, QtCore.Qt.Key.Key_Return)
        load.assert_not_called()
