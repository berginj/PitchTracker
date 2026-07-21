from __future__ import annotations

import json
from pathlib import Path

from app.events.event_bus import EventBus
from app.events.event_types import PitchAnalyzedEvent, PitchEndEvent
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.services.analysis import AnalysisServiceImpl
from app.services.recording import RecordingServiceImpl
from configs.settings import load_config
from contracts import StereoObservation


def _config():
    return load_config(Path(__file__).parents[2] / "configs" / "default.yaml")


def _observation(timestamp_ns: int = 1_000_000_000) -> StereoObservation:
    return StereoObservation(
        t_ns=timestamp_ns,
        left=(10.0, 10.0),
        right=(12.0, 10.0),
        X=0.0,
        Y=3.0,
        Z=50.0,
        quality=0.9,
        confidence=0.9,
    )


def _event(pitch_id: str, observations=None) -> PitchEndEvent:
    return PitchEndEvent(
        pitch_id=pitch_id,
        observations=list(observations or []),
        timestamp_ns=1_100_000_000,
        duration_ns=100_000_000,
    )


def _assert_claim_free_failure(event: PitchAnalyzedEvent, reason_code: str) -> None:
    summary = event.summary
    assert summary.measurement_status == "UNAVAILABLE"
    assert summary.speed_mph is None
    assert summary.speed_source is None
    assert summary.zone_row is None
    assert summary.zone_col is None
    assert summary.trajectory_plate_x_ft is None
    assert summary.trajectory_plate_y_ft is None
    assert summary.quality_diagnostics["strike_available"] is False
    assert summary.quality_diagnostics["movement_available"] is False
    assert summary.quality_diagnostics["plate_crossing_available"] is False
    assert reason_code in summary.quality_diagnostics["reason_codes"]
    assert reason_code in summary.observation_rejection_reasons


def test_empty_pitch_publishes_one_unavailable_terminal_event() -> None:
    bus = EventBus()
    terminal = []
    bus.subscribe(PitchAnalyzedEvent, terminal.append)
    service = AnalysisServiceImpl(bus, _config())
    service.start_analysis()

    try:
        bus.publish(_event("pitch_empty"))
        assert service.wait_for_idle(timeout=5.0)

        assert len(terminal) == 1
        _assert_claim_free_failure(terminal[0], "NO_OBSERVATIONS")
        assert service.get_session_summary().pitch_count == 1
        assert service.get_session_summary().strikes == 0
        assert service.get_session_summary().balls == 0
        stats = service.get_worker_stats()
        assert stats["completed"] == 1
        assert stats["failed"] == 0
    finally:
        service.stop_analysis()


def test_analysis_exception_publishes_failure_then_increments_worker_failed(monkeypatch) -> None:
    bus = EventBus()
    terminal = []
    bus.subscribe(PitchAnalyzedEvent, terminal.append)
    service = AnalysisServiceImpl(bus, _config())
    service.start_analysis()
    monkeypatch.setattr(
        service._analyzer,
        "analyze_pitch",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic fitter failure")),
    )

    try:
        bus.publish(_event("pitch_exception", [_observation()]))
        assert service.wait_for_idle(timeout=5.0)

        assert len(terminal) == 1
        _assert_claim_free_failure(terminal[0], "ANALYSIS_PIPELINE_EXCEPTION")
        assert terminal[0].summary.quality_diagnostics["exception_type"] == "RuntimeError"
        stats = service.get_worker_stats()
        assert stats["failed"] == 1
        assert stats["completed"] == 0
        assert service.get_session_summary().pitch_count == 1
    finally:
        service.stop_analysis()


def test_queue_drop_publishes_exactly_one_unavailable_result_for_duplicate_pitch(monkeypatch) -> None:
    bus = EventBus()
    terminal = []
    bus.subscribe(PitchAnalyzedEvent, terminal.append)
    service = AnalysisServiceImpl(bus, _config())
    service.start_analysis()
    monkeypatch.setattr(service._analysis_worker, "submit", lambda _event: False)
    event = _event("pitch_dropped", [_observation()])

    try:
        bus.publish(event)
        bus.publish(event)

        assert len(terminal) == 1
        _assert_claim_free_failure(terminal[0], "ANALYSIS_QUEUE_DROPPED")
        assert service.get_session_summary().pitch_count == 1
    finally:
        service.stop_analysis()


def test_recording_service_writes_unavailable_manifest_from_terminal_event(tmp_path) -> None:
    bus = EventBus()
    config = _config()
    analysis = AnalysisServiceImpl(bus, config)
    recording = RecordingServiceImpl(bus)
    recorder = PitchRecorder(config=config, session_dir=tmp_path, pitch_id="pitch_manifest")

    recording._pitch_recorder = recorder
    recording._pitch_active = True
    recording._current_pitch_id = "pitch_manifest"
    bus.subscribe(PitchAnalyzedEvent, recording._on_pitch_analyzed)
    analysis.start_analysis()

    try:
        bus.publish(_event("pitch_manifest"))
        assert analysis.wait_for_idle(timeout=5.0)

        manifest_path = recorder.get_pitch_dir() / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["measurement_status"] == "UNAVAILABLE"
        assert manifest["measured_speed_mph"] is None
        assert manifest["zone_row"] is None
        assert manifest["zone_col"] is None
        assert manifest["quality_diagnostics"]["reason_codes"] == ["NO_OBSERVATIONS"]
        assert manifest["quality_diagnostics"]["strike_available"] is False
        assert manifest["quality_diagnostics"]["movement_available"] is False
    finally:
        analysis.stop_analysis()
        recorder.close(force=True)
