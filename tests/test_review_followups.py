"""Regression journeys for recording roots and atomic historical pitch handoffs."""

from dataclasses import replace
import json

import pytest

from app.review.review_service import PitchScore, ReviewService
from app.review.playback_mapping import pitch_playback, read_timestamps
from app.review.session_loader import SessionLoader
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


def test_filtered_out_pitch_preserves_previous_player_and_review(workspace, monkeypatch, tmp_path):
    window, _pipeline = workspace
    previous = write_session(tmp_path / "previous")
    candidate = write_session(tmp_path / "candidate")
    for session, name in ((previous, "Previous Pitcher"), (candidate, "Other Pitcher")):
        for index in (1, 2):
            path = session / f"pitch_{index:05d}/manifest.json"
            content = json.loads(path.read_text(encoding="utf-8"))
            content["pitcher"] = {"schema_version": "pitcher_attribution.v1", "name": name}
            path.write_text(json.dumps(content), encoding="utf-8")
    assert window.navigate("sessions")
    page = window.page("sessions")
    page.open_selection(ReviewSelection(previous, pitch_id="pitch_00002", pitcher_name="Previous Pitcher"))
    selected = page.review.selection()
    service = page.review._service
    old_session = service.session
    monkeypatch.setattr("ui.review._session_controller.show_message_dialog", lambda *args, **kwargs: None)
    page.open_selection(ReviewSelection(candidate, pitch_id="pitch_00002", pitcher_name="Previous Pitcher"))
    assert service.session is old_session
    assert service.player_filter == "Previous Pitcher"
    assert page.review.selection() == window.navigation_context.review == selected
    assert service.current_frame_index == 2
    assert "73.6 mph" in page.review._feedback.labels["speed"].text()


@pytest.mark.parametrize("left_count,right_count", [(4, 3), (3, 4)])
def test_unequal_video_counts_reject_even_the_overlapping_pitch(tmp_path, left_count, right_count):
    path = write_session(tmp_path)
    session = SessionLoader.load_session(path, require_video=False)
    for side, count in (("left", left_count), ("right", right_count)):
        mapping = path / f"session_{side}_timestamps.csv"
        lines = mapping.read_text(encoding="utf-8").splitlines(keepends=True)
        mapping.write_text("".join(lines[:count + 1]), encoding="utf-8")
        assert len(read_timestamps(mapping, count)) == count
    mappings = pitch_playback(session, left_count, right_count)
    assert len(mappings) == 2
    assert all(mapping.frame_index is None and "unequal camera frame counts" in mapping.reason for mapping in mappings)
