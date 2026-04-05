from __future__ import annotations

import json

from app.review.session_loader import SessionLoader


def test_get_available_sessions_accepts_current_manifest_layout(tmp_path):
    session_dir = tmp_path / "bullpen_20260404-120000"
    session_dir.mkdir()
    (session_dir / "manifest.json").write_text(json.dumps({"session_id": "bullpen-1"}))

    sessions = SessionLoader.get_available_sessions(tmp_path)

    assert sessions == [session_dir]


def test_load_session_supports_current_manifest_names(tmp_path):
    session_dir = tmp_path / "bullpen_20260404-120000"
    session_dir.mkdir()

    (session_dir / "manifest.json").write_text(
        json.dumps(
            {
                "session_id": "bullpen-1",
                "session_left_video": "session_left.avi",
                "session_right_video": "session_right.avi",
                "session_left_timestamps": "session_left_timestamps.csv",
                "session_right_timestamps": "session_right_timestamps.csv",
            }
        )
    )
    (session_dir / "session_left.avi").write_text("")
    (session_dir / "session_right.avi").write_text("")

    pitch_dir = session_dir / "pitch_00001"
    pitch_dir.mkdir()
    (pitch_dir / "manifest.json").write_text(
        json.dumps(
            {
                "pitch_id": "pitch_00001",
                "left_video": "left.mp4",
                "right_video": "right.mp4",
                "left_timestamps": "left_timestamps.csv",
                "right_timestamps": "right_timestamps.csv",
            }
        )
    )

    loaded = SessionLoader.load_session(session_dir)

    assert loaded.session_id == "bullpen-1"
    assert len(loaded.pitches) == 1
    assert loaded.pitches[0].pitch_id == "pitch_00001"
    assert loaded.pitches[0].left_video_path.name == "left.mp4"
