"""Characterization tests for the ReviewService facade."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.review.review_service import PitchScore, ReviewService


def _session(tmp_path):
    left = tmp_path / "left.avi"
    right = tmp_path / "right.avi"
    left.write_bytes(b"")
    right.write_bytes(b"")
    pitch = MagicMock(pitch_id="pitch_00001")
    return MagicMock(
        session_id="session",
        left_video_path=left,
        right_video_path=right,
        original_config=None,
        pitches=[pitch],
    )


def test_load_session_opens_paired_videos_and_resets_scores(tmp_path):
    service = ReviewService()
    service._video_reader = MagicMock(total_frames=42)
    session = _session(tmp_path)

    with patch("app.review.review_service.SessionLoader.load_session", return_value=session):
        loaded = service.load_session(Path("session"))

    assert loaded is session
    service._video_reader.open_videos.assert_called_once_with(session.left_video_path, session.right_video_path)
    assert service._pitch_scores == {"pitch_00001": PitchScore.UNSCORED}


def test_seek_to_pitch_preserves_approximate_frame_semantics(tmp_path):
    service = ReviewService()
    service._session = _session(tmp_path)
    service._video_reader = MagicMock()
    service._video_reader.seek_to_frame.return_value = True

    assert service.seek_to_pitch(0)
    service._video_reader.seek_to_frame.assert_called_once_with(0)
    assert not service.seek_to_pitch(3)


def test_annotation_export_preserves_shape(tmp_path):
    service = ReviewService()
    service.add_annotation(4, "left", 10.0, 20.0, "ball")
    service.score_pitch("pitch_00001", PitchScore.GOOD)
    output = tmp_path / "annotations.json"

    service.export_annotations(output)

    import json

    data = json.loads(output.read_text())
    assert data["total_annotations"] == 1
    assert data["annotations"][0]["frame_index"] == 4
    assert data["pitch_scores"] == {"pitch_00001": "good"}
