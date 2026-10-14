"""Completed-session handoff and consistent selection across review surfaces."""

from unittest.mock import patch

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from app.services.orchestrator.runtime_status import FinalizedSession, RuntimeFailure
from scripts.ux_review_fixtures import SyntheticReviewReader, write_session
from tests import test_workspace_navigation as navigation
from ui.workspace.contracts import ReviewSelection

workspace = navigation.workspace


@pytest.fixture(autouse=True)
def synthetic_reader(monkeypatch):
    monkeypatch.setattr("app.review.review_service.VideoReader", SyntheticReviewReader)


def test_review_completed_session_opens_without_directory_dialog(workspace, tmp_path):
    window, pipeline = workspace
    path = write_session(tmp_path / "recordings")
    pipeline.set_status(recording_phase="completed", finalized_session=FinalizedSession("example-bullpen", path))
    assert window._primary_action == "review"
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory") as dialog:
        window._perform_primary_action()
        dialog.assert_not_called()
    assert window.navigation_context.review == ReviewSelection(path, "example-bullpen", "pitch_00001")
    assert window.page("sessions").review._service.current_frame_index == 1


@pytest.mark.parametrize("phase", ["recording", "finalizing"])
def test_review_request_cannot_open_pending_session(workspace, tmp_path, phase):
    window, pipeline = workspace
    path = write_session(tmp_path)
    pipeline.set_status(recording_phase=phase, active_session_dir=path, finalized_session=FinalizedSession("old", path))
    window._review_finalized_session()
    assert window.navigation_context.page == "live"


def test_failed_finalization_does_not_offer_handoff(workspace, tmp_path):
    window, pipeline = workspace
    pipeline.set_status(recording_phase="finalizing", failure=RuntimeFailure("stop_recording", "Disk write failed"),
                        finalized_session=FinalizedSession("old", tmp_path))
    window._review_finalized_session()
    assert window.navigation_context.page == "live"


def test_pitch_row_updates_video_metrics_location_and_identity_together(workspace, tmp_path):
    window, _ = workspace
    window.navigate("sessions")
    review = window.page("sessions").review
    path = write_session(tmp_path)
    review.open_session(ReviewSelection(path, pitch_id="pitch_00002"))
    assert review.selection().pitch_id == "pitch_00002"
    assert "73.6 mph" in review._feedback.labels["speed"].text()
    assert "+1.10 ft" in review._feedback.labels["location"].text()
    assert review._service.current_frame_index == 2
    review._pitch_list._pitch_list.setCurrentRow(0)
    assert review.selection().pitch_id == "pitch_00001"
    assert review._service.current_frame_index == 1
    assert "72.6 mph" in review._feedback.labels["speed"].text()
    assert window.navigation_context.review.pitch_id == "pitch_00001"


def test_capture_browsing_preserves_active_session_and_does_no_detection(workspace, tmp_path):
    window, pipeline = workspace
    path = write_session(tmp_path / "recordings")
    active = tmp_path / "recordings/current"
    pipeline.set_status(capture_phase="live", recording_phase="recording", session_id="active", active_session_dir=active)
    window.navigate("sessions")
    review = window.page("sessions").review
    with patch.object(review._service, "run_detection_on_current_frame") as detect:
        review.open_session(ReviewSelection(path))
        review._pitch_list._pitch_list.setCurrentRow(1)
        detect.assert_not_called()
    assert pipeline.status.recording_phase == "recording"
    assert pipeline.shutdown_calls == 0
    assert "Active: active" in window._identity.text()


@pytest.mark.parametrize("state", ["missing-video", "invalid-mapping", "legacy", "empty", "rejected"])
def test_degraded_review_is_explicit_and_replaces_previous_pitch(workspace, tmp_path, state):
    window, _ = workspace
    window.navigate("sessions")
    review = window.page("sessions").review
    review.open_session(ReviewSelection(write_session(tmp_path, "good")))
    path = write_session(tmp_path, state=state)
    review.open_session(ReviewSelection(path, pitch_id=None if state == "empty" else "pitch_00002"))
    assert review.selection().session_dir == path
    if state in {"missing-video", "invalid-mapping"}:
        assert review._left_display._current_frame is None
        assert "unavailable" in review._feedback.labels["playback"].text()
        assert not review._controls.isEnabled()
        review._playback_ctrl.toggle_playback()
        assert not review._playback_ctrl.is_playing
    elif state == "empty":
        assert review.selection().pitch_id is None
        assert "no recorded pitches" in review._feedback.labels["identity"].text()
    else:
        assert "unavailable" in review._feedback.labels["speed"].text()


def test_invalid_mapping_can_only_leave_pitch_association_explicitly(workspace, tmp_path):
    window, _ = workspace
    window.navigate("sessions")
    review = window.page("sessions").review
    review.open_session(ReviewSelection(write_session(tmp_path, state="invalid-mapping")))
    assert not review._controls.isEnabled()
    review.browse_session_video()
    assert review.selection().pitch_id is None
    assert review._controls.isEnabled()
    assert "no pitch association" in review._feedback.labels["identity"].text()


@pytest.mark.parametrize("size", [(1366, 768), (1024, 768), (800, 600)])
def test_review_reaches_feedback_and_playback_without_horizontal_overflow(workspace, tmp_path, qtbot, size):
    window, _ = workspace
    for filename in ("segoeui.ttf", "segoeuib.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{filename}")
    from ui.themes import get_style_manager
    get_style_manager().apply_to_app(QtWidgets.QApplication.instance())
    window.navigate("sessions")
    review = window.page("sessions").review
    review.open_session(ReviewSelection(write_session(tmp_path)))
    window.resize(*size)
    qtbot.wait(20)
    assert window.size() == QtCore.QSize(*size)
    scroll = review.centralWidget()
    assert scroll.horizontalScrollBar().maximum() == 0
    for widget in (review._controls._play_pause_btn, review._feedback.labels["source"], review._pitch_list._pitch_list):
        scroll.ensureWidgetVisible(widget)
        qtbot.wait(5)
        assert widget.isVisibleTo(window)
    assert review._controls._play_pause_btn.accessibleName()


def test_queued_video_refresh_cannot_restore_earlier_pitch(workspace, tmp_path, qtbot):
    window, _ = workspace
    window.navigate("sessions")
    review = window.page("sessions").review
    review.open_session(ReviewSelection(write_session(tmp_path)))
    QtCore.QTimer.singleShot(0, review._update_video_displays)
    QtCore.QTimer.singleShot(0, review._playback_ctrl._on_playback_tick)
    review._pitch_list._pitch_list.setCurrentRow(1)
    qtbot.wait(10)
    assert review.selection().pitch_id == "pitch_00002"
    assert review._left_display._current_frame[0, 0, 0] == 90
    assert "73.6" in review._feedback.labels["speed"].text()


def test_failed_open_preserves_previous_context_and_explains_recovery(workspace, tmp_path):
    window, _ = workspace
    window.navigate("sessions")
    page = window.page("sessions")
    good = write_session(tmp_path)
    page.open_selection(ReviewSelection(good))
    with patch("ui.review._session_controller.show_message_dialog"):
        page.open_selection(ReviewSelection(tmp_path / "missing"))
    assert window.navigation_context.review.session_dir == good
    assert "try again" in page._selection_label.text()


def test_configured_history_root_is_used_without_changing_capture(qtbot, tmp_path):
    from ui.workspace.sessions_page import SessionsPage
    root = tmp_path / "custom-recordings"
    session = write_session(root)
    page = SessionsPage(root)
    qtbot.addWidget(page)
    assert page._sessions.currentData() == session
    page._open_selected()
    assert page.review.selection().session_dir == session
    assert page.shutdown_for_workspace()


def test_missing_calibration_never_enables_projected_overlay(workspace, tmp_path):
    window, _ = workspace
    window.navigate("sessions")
    review = window.page("sessions").review
    review.open_session(ReviewSelection(write_session(tmp_path)))
    review._toggle_trajectory_overlay(True)
    assert not review._trajectory_ctrl.overlay_enabled
    assert "unavailable" in review.statusBar().currentMessage()
    review._service.session.calibration = {"focal_length_px": 1000.}
    review._trajectory_ctrl.init_renderers()
    assert not review._trajectory_ctrl.overlay_available
