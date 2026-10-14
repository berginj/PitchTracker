"""Recorded pitch identity must never depend on guessed video positions."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.review.review_service import ReviewService
from app.review.recorded_metrics import recorded_metrics
from app.services.orchestrator.runtime_status import RuntimeStatus
from scripts.ux_review_fixtures import SyntheticReviewReader, write_session


@pytest.fixture
def review(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app.review.review_service.VideoReader", SyntheticReviewReader)
    service = ReviewService()
    yield service
    service.close()


def test_pitch_navigation_uses_recorded_encoded_positions(review, tmp_path):
    path = write_session(tmp_path)
    review.load_session(path)
    assert review.seek_to_pitch(1)
    assert review.current_frame_index == 2
    frame, _ = review.get_current_frames()
    assert frame[0, 0, 0] == 90
    assert review.seek_to_pitch(0)
    assert review.current_frame_index == 1


@pytest.mark.parametrize("state", ["invalid-mapping", "missing-video"])
def test_unavailable_video_preserves_metrics_and_clears_playback(review, tmp_path, state):
    review.load_session(write_session(tmp_path, state=state))
    assert len(review.session.pitches) == 2
    assert not review.seek_to_pitch(1)
    assert review.get_current_frames() == (None, None)
    assert review.playback_for_pitch(1).reason
    assert recorded_metrics(review.session.pitches[1].manifest).speed == "73.6 mph"


def test_active_path_blocked_while_other_same_named_history_is_browsable(review, tmp_path):
    path = write_session(tmp_path, "history")
    active = tmp_path / "active"
    review.update_runtime(RuntimeStatus(sequence=1, capture_phase="live", recording_phase="recording",
                                        session_id="history", active_session_dir=active))
    review.load_session(path)
    assert review.session.session_dir == path
    with pytest.raises(ValueError, match="still being recorded"):
        review.load_session(active)
    with pytest.raises(RuntimeError, match="Stop runtime capture"):
        review.run_detection_on_current_frame()
    assert review.session.session_dir == path


def test_browsing_does_not_run_detection(review, tmp_path):
    with patch.object(review, "run_detection_on_current_frame") as detect:
        review.load_session(write_session(tmp_path))
        review.seek_to_pitch(1)
        review.get_current_frames()
        detect.assert_not_called()


@pytest.mark.parametrize("status", ["REJECTED", "UNAVAILABLE", "UNKNOWN"])
def test_historical_invalid_or_unknown_claims_are_explicit(tmp_path, status):
    manifest = {"measurement_status": status, "measured_speed_mph": 88., "is_strike": False,
                "trajectory": {"plate_crossing_xyz_ft": [0., 2., 0.]}}
    metrics = recorded_metrics(manifest)
    assert metrics.speed == metrics.location == "unavailable"
    assert metrics.result == "UNAVAILABLE"
    assert "reference unavailable" in metrics.provenance


def test_corrupt_mapping_never_falls_back_to_index_times_100(review, tmp_path):
    path = write_session(tmp_path)
    mapping = path / "session_right_timestamps.csv"
    text = mapping.read_text()
    mapping.write_text(text.replace("1,accepted", "0,accepted"))
    review.load_session(path)
    assert not review.seek_to_pitch(1)
    assert "contiguous" in review.playback_for_pitch(1).reason


def test_stale_runtime_cannot_unblock_active_session(review, tmp_path):
    active = tmp_path / "active"
    status = RuntimeStatus(sequence=2, active_session_dir=active, recording_phase="finalizing")
    review.update_runtime(status)
    review.update_runtime(replace(status, sequence=1, active_session_dir=None))
    assert not review.can_open_session(active)


@pytest.mark.parametrize("old,new", [
    ("2,accepted", "2,unknown"),
    ("2000000000", "0"),
    ("3,accepted,3000000000,synthetic-epoch", "3,accepted,3000000000,other-epoch"),
    ("3,accepted,3000000000,synthetic-epoch", ""),
])
def test_invalid_write_time_epoch_and_count_mapping_fail_closed(review, tmp_path, old, new):
    path = write_session(tmp_path)
    mapping = path / "session_left_timestamps.csv"
    mapping.write_text(mapping.read_text().replace(old, new))
    review.load_session(path)
    assert not review.seek_to_pitch(0)
    assert review.playback_for_pitch(0).reason
