"""Terminal persistence retries retain one verdict using real evidence files."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.contracts import PitchSummary
from app.events.event_bus import EventBus
from app.events.event_types import PitchAnalyzedEvent
from app.pipeline.recording import evidence_package
from app.pipeline.recording.evidence_package import load_evidence_package
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.services.recording import RecordingServiceImpl
from configs.settings import load_config


@pytest.mark.parametrize("failure_stage", ["stream", "manifest"])
def test_failed_terminal_evidence_write_retries_without_duplicate_verdict(
    tmp_path: Path, monkeypatch, failure_stage: str,
) -> None:
    service = RecordingServiceImpl(EventBus())
    service._session_active = True
    service._session_name = "retry"
    service._session_recorder = MagicMock()
    service._session_recorder.get_session_dir.return_value = tmp_path
    service._frame_worker = MagicMock()
    pitch = PitchRecorder(load_config(Path("configs/default.yaml")), tmp_path, "pitch_1")
    service._completed_pitch_recorders["pitch_1"] = pitch
    service._pitch_lifecycle_metadata["pitch_1"] = {"pitch_end": {}}
    summary = PitchSummary("pitch_1", 1, 2, False, None, None, 0.0, 0.0, None, None, 1)
    real_write = evidence_package._atomic_write_text
    fail_writes = True

    def failing_write(path: Path, content: str) -> None:
        matches = path.suffix == ".jsonl" if failure_stage == "stream" else path.name == "manifest.json"
        if fail_writes and matches:
            raise OSError("evidence disk unavailable")
        real_write(path, content)

    monkeypatch.setattr(evidence_package, "_atomic_write_text", failing_write)
    service._on_pitch_analyzed(PitchAnalyzedEvent("pitch_1", summary, None))
    with pytest.raises(RuntimeError, match="manifests are still pending"):
        service.stop_session()
    assert service._completed_pitch_recorders["pitch_1"] is pitch
    assert "pitch_1" in service._pending_analysis_events
    fail_writes = False
    service.stop_session()
    package = load_evidence_package(pitch.get_pitch_dir() / "evidence" / "manifest.json")
    verdicts = package["streams"]["pitch_verdict"]
    assert len(verdicts) == 1
    assert verdicts[0]["pitch_id"] == "pitch_1"
    assert not service._pending_analysis_events
    assert not service.is_recording_session()
