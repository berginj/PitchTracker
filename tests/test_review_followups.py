"""Regression journeys for recording roots and atomic historical pitch handoffs."""

from dataclasses import replace

import pytest

from app.review.review_service import PitchScore, ReviewService
from app.services.orchestrator.runtime_status import RuntimeStatus
from scripts.ux_review_fixtures import SyntheticReviewReader, write_session
from tests import test_workspace_navigation as navigation
from tests import test_workspace_session_commands as commands
from ui.coaching.session_commands import PrepareSession
from ui.workspace.contracts import ReviewSelection

workspace = navigation.workspace
session_workspace = commands.session_workspace


@pytest.fixture(autouse=True)
def synthetic_reader(monkeypatch):
    monkeypatch.setattr("app.review.review_service.VideoReader", SyntheticReviewReader)


@pytest.fixture
def review():
    service = ReviewService()
    yield service
    service.close()


def test_preparation_and_history_use_the_same_custom_directory(session_workspace, qtbot, tmp_path):
    window, pipeline = session_workspace
    live = window.page("live")
    root = tmp_path / "custom-recordings"
    historical = write_session(root)
    config = replace(live._config, recording=replace(live._config.recording, output_dir=str(root)))
    prepared = PrepareSession(config, live._config_path, "sim-left", "sim-right", "new-session", "Example Pitcher")
    runner = live._session_ctrl.runner
    assert runner.submit("prepare", prepared)
    qtbot.waitUntil(lambda: not runner.busy)
    assert not runner.state.failure_message
    assert pipeline.record_directory == live.recordings_directory() == root
    assert window.navigate("sessions")
    assert window.page("sessions")._sessions.currentData() == historical
    assert pipeline.status.capture_phase == "live"


@pytest.mark.parametrize("active_known", [False, True])
def test_recording_start_preserves_independent_history(review, tmp_path, active_known):
    historical = write_session(tmp_path / "history")
    active = tmp_path / "active"
    review.update_runtime(RuntimeStatus(sequence=1, capture_phase="live", recording_phase="starting",
                                        pending_operation="start_recording",
                                        active_session_dir=active if active_known else None))
    assert review.can_open_session(historical)
    review.load_session(historical)
    assert review.session.session_dir == historical
    if active_known:
        assert not review.can_open_session(active)
        with pytest.raises(ValueError, match="still being recorded"):
            review.load_session(active)
        assert review.session.session_dir == historical


def test_missing_requested_pitch_preserves_service_state(review, tmp_path):
    previous = review.load_session(write_session(tmp_path / "previous"))
    assert review.seek_to_pitch(1)
    review.score_pitch("pitch_00002", PitchScore.GOOD)
    candidate = write_session(tmp_path / "candidate")
    with pytest.raises(ValueError, match="Requested pitch"):
        review.load_session(candidate, pitch_id="missing-pitch")
    assert review.session is previous
    assert review.current_frame_index == 2
    assert review.pitch_scores["pitch_00002"] == PitchScore.GOOD
    assert review.playback_available


@pytest.mark.parametrize("same_session", [False, True])
def test_missing_pitch_handoff_preserves_the_entire_review(workspace, monkeypatch, tmp_path, same_session):
    window, _pipeline = workspace
    assert window.navigate("sessions")
    page = window.page("sessions")
    previous = write_session(tmp_path / "previous")
    page.open_selection(ReviewSelection(previous, pitch_id="pitch_00002"))
    review = page.review
    selection = review.selection()
    session = review._service.session
    feedback = review._feedback.labels["speed"].text()
    candidate = previous if same_session else write_session(tmp_path / "candidate")
    messages = []
    monkeypatch.setattr("ui.review._session_controller.show_message_dialog", lambda *args, **kwargs: messages.append(args))
    page.open_selection(ReviewSelection(candidate, pitch_id="missing-pitch"))
    assert messages
    assert review.selection() == window.navigation_context.review == selection
    assert review._service.session is session
    assert review._service.current_frame_index == 2
    assert review._feedback.labels["speed"].text() == feedback
    assert "try again" in page._selection_label.text()
