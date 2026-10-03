"""Retry and terminal-event regressions without cameras or codec dependencies."""

from pathlib import Path
import threading
from unittest.mock import MagicMock

import pytest

from app.events.event_bus import EventBus
from app.events.event_types import PitchAnalyzedEvent, PitchEndEvent
from app.contracts import PitchSummary
from app.services.recording import RecordingServiceImpl


def _active_recording(tmp_path: Path) -> RecordingServiceImpl:
    service = RecordingServiceImpl(EventBus())
    service._session_active = True
    service._session_name = "retry"
    service._session_recorder = MagicMock()
    service._session_recorder.get_session_dir.return_value = tmp_path
    service._frame_worker = MagicMock()
    service._decision_journal = MagicMock()
    service._decision_journal.stats.return_value = {
        "dropped_required": 0, "write_error": None, "accepted": 7, "written": 7,
    }
    return service


@pytest.mark.parametrize("failure", ["drain", "manifest"])
def test_stop_retry_preserves_journal_reference_and_completeness(tmp_path, failure):
    service = _active_recording(tmp_path)
    journal = service._decision_journal
    recorder = service._session_recorder
    if failure == "drain":
        service._frame_worker.stop.side_effect = [False, True]
    else:
        recorder.stop_session.side_effect = [OSError("manifest unavailable"), None]
    with pytest.raises((RuntimeError, OSError)):
        service.stop_session()
    assert service.is_recording_session()
    assert service._pending_journal_manifest == "evidence_journal/manifest.json"
    assert service._pending_journal_complete is True
    service.stop_session()
    assert not service.is_recording_session()
    journal.close.assert_called_once_with()
    final_call = recorder.stop_session.call_args.kwargs
    assert final_call["decision_evidence_manifest"] == "evidence_journal/manifest.json"
    assert final_call["decision_evidence_complete"] is True


def test_pause_timeout_remains_retryable(tmp_path):
    service = _active_recording(tmp_path)
    service._frame_worker.wait_idle.side_effect = [False, True]
    with pytest.raises(RuntimeError, match="still draining"):
        service.pause_session()
    assert service._inputs_suspended and not service._session_paused
    service.pause_session()
    assert service._session_paused


def _terminal_event():
    summary = PitchSummary("pitch_1", 1, 2, False, None, None, 0.0, 0.0, None, None, 1)
    return PitchAnalyzedEvent("pitch_1", summary, None)


def test_early_analysis_waits_for_recording_end_snapshot(tmp_path):
    service = _active_recording(tmp_path)
    pitch = MagicMock()
    service._pitch_recorder = pitch
    service._pitch_active = True
    service._current_pitch_id = "pitch_1"
    service._pitch_lifecycle_metadata["pitch_1"] = {"pitch_start": {}}
    entered, release = threading.Event(), threading.Event()

    def add_snapshot(*args, **kwargs):
        entered.set()
        assert release.wait(2)

    pitch.add_analysis_observations.side_effect = add_snapshot
    thread = threading.Thread(target=service._on_pitch_end, args=(PitchEndEvent("pitch_1", [], 2, 1),))
    try:
        thread.start()
        assert entered.wait(2)
        service._on_pitch_analyzed(_terminal_event())
        pitch.write_manifest.assert_not_called()
        release.set()
        thread.join(2)
        assert not thread.is_alive()
        pitch.write_manifest.assert_called_once()
        assert not service._pending_analysis_events
    finally:
        release.set()
        thread.join(2)


def test_manifest_error_retains_terminal_result_for_retry(tmp_path):
    service = _active_recording(tmp_path)
    pitch = MagicMock()
    service._completed_pitch_recorders["pitch_1"] = pitch
    service._pitch_lifecycle_metadata["pitch_1"] = {"pitch_end": {}}
    pitch.write_manifest.side_effect = OSError("disk unavailable")
    service._on_pitch_analyzed(_terminal_event())
    with pytest.raises(RuntimeError, match="manifests are still pending"):
        service.stop_session()
    assert service.is_recording_session()
    assert "pitch_1" in service._pitch_lifecycle_metadata
    pitch.write_manifest.side_effect = None
    service.stop_session()
    assert not service.is_recording_session()
    assert not service._pending_analysis_events
