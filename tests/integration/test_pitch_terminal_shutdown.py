"""Real analysis queues and recording subscriptions survive pause/stop ordering."""

import json
from pathlib import Path
import threading
from unittest.mock import MagicMock

import pytest

from app.contracts import PitchSummary
from app.events.event_types import PitchEndEvent
from app.services.analysis import AnalysisServiceImpl
from app.services.orchestrator import PipelineOrchestrator
from app.services.recording import RecordingServiceImpl
from configs.settings import load_config
from contracts import StereoObservation


@pytest.mark.parametrize("operation", ["pause_recording", "stop_recording"])
def test_accepted_analysis_is_durable_before_pause_or_stop(tmp_path, operation, monkeypatch):
    config = load_config(Path(__file__).resolve().parents[2] / "configs/default.yaml")
    orchestrator = PipelineOrchestrator(backend="sim")
    recorder = RecordingServiceImpl(orchestrator._event_bus)
    analysis = AnalysisServiceImpl(orchestrator._event_bus, config)
    recorder._session_active = True
    recorder._session_name = "terminal"
    recorder._session_recorder = MagicMock()
    recorder._session_recorder.get_session_dir.return_value = tmp_path
    pitch_dir = tmp_path / "pitch_00001"
    pitch_dir.mkdir()
    pitch = MagicMock()
    pitch.get_pitch_dir.return_value = pitch_dir
    writes = []

    def write_manifest(summary, _config, **kwargs):
        writes.append(summary.pitch_id)
        (pitch_dir / "manifest.json").write_text(json.dumps({"pitch_id": summary.pitch_id}))

    pitch.write_manifest.side_effect = write_manifest
    recorder._pitch_recorder = pitch
    recorder._pitch_active = True
    recorder._current_pitch_id = "pitch_00001"
    recorder._frame_worker.start()
    recorder._subscribe_to_events()
    started, release, done = threading.Event(), threading.Event(), threading.Event()
    errors = []

    def blocked_analysis(**kwargs):
        started.set()
        assert release.wait(3)
        return PitchSummary(
            "pitch_00001", 1, 2, False, None, None, 0.0, 0.0, None, None, 1,
        )

    monkeypatch.setattr(analysis._analyzer, "analyze_pitch", blocked_analysis)
    analysis.start_analysis(session_id="terminal")
    end = PitchEndEvent("pitch_00001", [StereoObservation(1, (0, 0), (0, 0), 0, 3, 1, 1)], 2, 1)
    orchestrator._pitch_tracker = MagicMock()
    orchestrator._pitch_tracker.force_end.side_effect = lambda: orchestrator._event_bus.publish(end)
    orchestrator._recording_service = recorder
    orchestrator._analysis_service = analysis
    orchestrator._recording_active = True

    def operate():
        try:
            getattr(orchestrator, operation)()
        except Exception as exc:
            errors.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=operate)
    try:
        thread.start()
        assert started.wait(2)
        assert not done.is_set()
        assert not (pitch_dir / "manifest.json").exists()
        release.set()
        assert done.wait(3)
        assert not errors
        assert writes == ["pitch_00001"]
        assert json.loads((pitch_dir / "manifest.json").read_text())["pitch_id"] == "pitch_00001"
    finally:
        release.set()
        thread.join(3)
        analysis.stop_analysis()
        if recorder.is_recording_session():
            recorder.stop_session()
