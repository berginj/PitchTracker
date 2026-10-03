"""Close ownership survives terminal success and concurrent lifecycle events."""

from pathlib import Path
import threading
from unittest.mock import MagicMock

import pytest

from app.contracts import PitchSummary
from app.events.event_bus import EventBus
from app.events.event_types import PitchAnalyzedEvent
from app.pipeline.recording.evidence_package import load_evidence_package
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.services.recording import RecordingServiceImpl
from configs.settings import load_config
from contracts import Frame, StereoObservation


def _session(tmp_path: Path) -> RecordingServiceImpl:
    service = RecordingServiceImpl(EventBus())
    service._session_active = True
    service._session_name = "retry"
    service._session_recorder = MagicMock()
    service._session_recorder.get_session_dir.return_value = tmp_path
    service._frame_worker = MagicMock()
    return service


def _pitch(tmp_path: Path) -> PitchRecorder:
    pitch = PitchRecorder(load_config(Path("configs/default.yaml")), tmp_path, "pitch_1")
    pitch._save_observations = True
    pitch.add_observation(StereoObservation(1, (0, 0), (0, 0), 0, 2, 0, 1))
    return pitch


def _terminal() -> PitchAnalyzedEvent:
    summary = PitchSummary("pitch_1", 1, 2, False, None, None, 0.0, 0.0, None, None, 1)
    return PitchAnalyzedEvent("pitch_1", summary, None)


def test_post_roll_close_does_not_retain_an_already_analyzed_recorder(tmp_path):
    service, pitch = _session(tmp_path), _pitch(tmp_path)
    service._pitch_recorder, service._pitch_active = pitch, True
    service._current_pitch_id = "pitch_1"
    service._pitch_lifecycle_metadata["pitch_1"] = {"pitch_end": {}}
    service._on_pitch_analyzed(_terminal())
    assert not service._pending_analysis_events
    with service._lock:
        service._stop_pitch_internal()
    assert not service._completed_pitch_recorders
    assert not service._pending_pitch_closes


@pytest.mark.parametrize("operation", ["pause_session", "stop_session"])
def test_terminal_success_cannot_discard_failed_close(tmp_path, monkeypatch, operation):
    service, pitch = _session(tmp_path), _pitch(tmp_path)
    service._pitch_recorder, service._pitch_active = pitch, True
    service._current_pitch_id = "pitch_1"
    service._pitch_lifecycle_metadata["pitch_1"] = {"pitch_end": {}}
    real_export = pitch._export_observations
    export = MagicMock(side_effect=OSError("observation export unavailable"))
    monkeypatch.setattr(pitch, "_export_observations", export)
    with pytest.raises(OSError):
        getattr(service, operation)()
    service._on_pitch_analyzed(_terminal())
    assert not service._completed_pitch_recorders
    assert not service._pending_analysis_events
    assert service._pending_pitch_closes["pitch_1"] is pitch
    assert (pitch.get_pitch_dir() / "manifest.json").exists()
    with pytest.raises(OSError):
        getattr(service, operation)()
    assert service._pending_pitch_closes["pitch_1"] is pitch
    assert service.is_recording_session()
    export.side_effect = real_export
    getattr(service, operation)()
    assert export.call_count == 3
    assert not service._pending_pitch_closes
    assert (pitch.get_pitch_dir() / "observations" / "stereo_observations.json").exists()
    package = load_evidence_package(pitch.get_pitch_dir() / "evidence" / "manifest.json")
    assert len(package["streams"]["pitch_verdict"]) == 1
    if operation == "pause_session":
        assert service.is_paused()
        service.stop_session()
    assert not service.is_recording_session()


def _run_thread(action, errors, done=None):
    try:
        action()
    except Exception as exc:
        errors.append(exc)
    finally:
        if done is not None:
            done.set()


def test_pending_close_and_terminal_manifest_do_not_overlap(tmp_path, monkeypatch):
    service, pitch = _session(tmp_path), _pitch(tmp_path)
    service._pending_pitch_closes["pitch_1"] = pitch
    service._completed_pitch_recorders["pitch_1"] = pitch
    service._pitch_lifecycle_metadata["pitch_1"] = {"pitch_end": {}}
    entered, release, manifest_entered = threading.Event(), threading.Event(), threading.Event()
    real_export, real_manifest = pitch._export_observations, pitch.write_manifest

    def blocked_export():
        entered.set()
        assert release.wait(2)
        real_export()

    def write_manifest(*args, **kwargs):
        manifest_entered.set()
        real_manifest(*args, **kwargs)

    monkeypatch.setattr(pitch, "_export_observations", blocked_export)
    monkeypatch.setattr(pitch, "write_manifest", write_manifest)
    errors = []
    close_thread = threading.Thread(target=_run_thread, args=(service.retry_completed_pitch_closes, errors))
    terminal_thread = threading.Thread(target=service._on_pitch_analyzed, args=(_terminal(),))
    try:
        close_thread.start()
        assert entered.wait(2)
        assert service._pitch_artifact_lock.locked()
        assert service._lock.acquire(blocking=False)
        service._lock.release()
        terminal_thread.start()
        assert not manifest_entered.wait(0.1)
        release.set()
        close_thread.join(2)
        terminal_thread.join(2)
        assert not close_thread.is_alive() and not terminal_thread.is_alive()
        assert not errors and manifest_entered.is_set()
        assert not service._pending_pitch_closes and not service._completed_pitch_recorders
    finally:
        release.set()
        close_thread.join(2)
        if terminal_thread.ident is not None:
            terminal_thread.join(2)


def test_frame_admission_finishes_before_pause_can_drain(tmp_path, monkeypatch):
    service = _session(tmp_path)
    from app.services.recording.worker import BoundedRecordingWorker
    service._frame_worker = BoundedRecordingWorker(service._record_frame_sync)
    assert service._frame_worker.start()
    entered, release, paused = threading.Event(), threading.Event(), threading.Event()
    real_submit = service._frame_worker.submit

    def blocked_submit(item):
        entered.set()
        assert release.wait(2)
        return real_submit(item)

    monkeypatch.setattr(service._frame_worker, "submit", blocked_submit)
    frame = Frame("left", 1, 1, None, 1, 1, "GRAY8")
    errors = []
    publisher = threading.Thread(target=_run_thread, args=(lambda: service.record_frame("left", frame), errors))
    pauser = threading.Thread(target=_run_thread, args=(service.pause_session, errors, paused))
    try:
        publisher.start()
        assert entered.wait(2)
        acquired = service._lock.acquire(blocking=False)
        if acquired:
            service._lock.release()
        assert not acquired
        pauser.start()
        assert not paused.wait(0.1)
        release.set()
        publisher.join(2)
        pauser.join(2)
        assert not errors and paused.is_set()
        service._session_recorder.write_frame.assert_called_once_with("left", frame)
        service.record_frame("left", frame)
        assert service._frame_worker.stats().submitted == 1
    finally:
        release.set()
        publisher.join(2)
        if pauser.ident is not None:
            pauser.join(2)
        assert service._frame_worker.stop(drain=True)
