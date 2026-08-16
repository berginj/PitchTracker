from __future__ import annotations

from pathlib import Path

from ui.review._session_controller import SessionController


def test_quarantine_session_moves_recordings_to_recoverable_trash(tmp_path: Path) -> None:
    session_dir = tmp_path / "session-001"
    session_dir.mkdir()
    artifact = session_dir / "manifest.json"
    artifact.write_text("{}", encoding="utf-8")

    quarantine_dir = SessionController._quarantine_session(session_dir)

    assert not session_dir.exists()
    assert quarantine_dir.parent == tmp_path / ".pitchtracker-trash"
    assert quarantine_dir.is_dir()
    assert (quarantine_dir / "manifest.json").read_text(encoding="utf-8") == "{}"
