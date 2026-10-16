"""Operator changes bind at pitch boundaries and survive delayed analysis."""

from threading import Event, Lock, Thread
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.events.event_types import PitchAnalyzedEvent, PitchEndEvent, PitchStartEvent
from app.pipeline.recording.manifest import create_pitch_manifest
from app.services.analysis.pitch_terminal import PitchTerminalHandler
from app.services.analysis.session_aggregation import SessionAggregator
from app.services.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from configs.pitchers import add_pitcher, load_pitchers, rename_pitcher, remove_pitcher
from contracts.pitcher import PitcherSelection


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return PipelineOrchestrator(backend="sim")


def pitch(index=1):
    return SimpleNamespace(pitch_index=index, start_ns=100, end_ns=200, duration_ns=lambda: 100,
                           observations=[], ray_observations=[])


def test_switch_during_pitch_preserves_start_and_delayed_summary(pipeline):
    bus, coordinator = pipeline._event_bus, pipeline._event_coordinator
    starts, ends, analyzed = [], [], []
    for event, target in ((PitchStartEvent, starts), (PitchEndEvent, ends), (PitchAnalyzedEvent, analyzed)):
        bus.subscribe(event, target.append)
    pipeline.change_pitcher("Example Pitcher")
    coordinator.on_pitch_start(1, pitch())
    receipt = pipeline.change_pitcher("Next Pitcher")
    assert receipt == PitcherSelection("Example Pitcher", "Next Pitcher", "pitch_00001")
    coordinator.on_pitch_end(pitch())
    assert starts[0].pitcher_name == ends[0].pitcher_name == "Example Pitcher"
    assert pipeline.runtime_status().pitcher == PitcherSelection("Next Pitcher")
    coordinator.on_pitch_start(2, pitch(2))
    coordinator.on_pitch_end(pitch(2))
    assert ends[1].pitcher_name == "Next Pitcher"
    aggregator = SessionAggregator()
    aggregator.reset("synthetic")
    handler = PitchTerminalHandler(bus, MagicMock(), aggregator, MagicMock(), Lock())
    handler.handle_pitch_end(ends[0])  # Terminal analysis completes after the switch.
    assert analyzed[0].summary.pitcher_name == "Example Pitcher"
    manifest = create_pitch_manifest(analyzed[0].summary, None)
    assert manifest["pitcher"] == {"schema_version": "pitcher_attribution.v1", "name": "Example Pitcher",
                                   "basis": "operator_selected_at_pitch_start"}


def test_rejected_pitch_and_latest_pending_selection_have_safe_boundary(pipeline):
    coordinator = pipeline._event_coordinator
    pipeline.change_pitcher("First")
    coordinator.on_pitch_start(1, pitch())
    pipeline.change_pitcher("Second")
    pipeline.change_pitcher("Third")
    coordinator.on_pitch_rejected(pitch(), "Too short")
    assert pipeline.runtime_status().pitcher == PitcherSelection("Third")


def test_pitch_start_and_change_are_serialized_without_blocking_status(pipeline):
    entered, release, completed = Event(), Event(), Event()
    pipeline.change_pitcher("First")

    def blocked_start(_event):
        entered.set()
        assert release.wait(5)

    def request():
        pipeline.change_pitcher("Second")
        completed.set()

    pipeline._event_bus.subscribe(PitchStartEvent, blocked_start)
    started = Thread(target=lambda: pipeline._event_coordinator.on_pitch_start(1, pitch()))
    changer = Thread(target=request)
    started.start()
    try:
        assert entered.wait(2)
        changer.start()
        assert not completed.wait(.02)
        assert pipeline.runtime_status().pitcher.active_name == "First"
    finally:
        release.set()
        started.join(5)
        if changer.ident is not None:
            changer.join(5)
    assert completed.is_set() and not started.is_alive() and not changer.is_alive()
    assert pipeline.runtime_status().pitcher.pending_name == "Second"


def test_change_to_current_pitcher_cancels_pending_request(pipeline):
    pipeline.change_pitcher("First")
    pipeline._event_coordinator.on_pitch_start(1, pitch())
    pipeline.change_pitcher("Second")
    pipeline.change_pitcher("First")
    assert pipeline.runtime_status().pitcher.pending_name is None


def test_ramp_up_keeps_the_pitch_that_already_started_attributed(pipeline):
    from app.pipeline.pitch_tracking_v2 import PitchStateMachineV2, PitchConfig
    coordinator = pipeline._event_coordinator
    tracker = PitchStateMachineV2(PitchConfig(min_active_frames=3, min_duration_ms=0, use_plate_gate=False))
    coordinator.wire_pitch_tracker(tracker)
    coordinator.set_pitch_tracker(tracker)
    starts = []
    pipeline._event_bus.subscribe(PitchStartEvent, starts.append)
    pipeline.change_pitcher("First")
    frame = SimpleNamespace(timestamp_ns=1, lane_count=1, plate_count=0, observations=[])
    coordinator.on_stereo_frame_processed(frame)
    receipt = pipeline.change_pitcher("Second")
    assert receipt.active_name == "First" and receipt.pending_name == "Second"
    for timestamp in (2, 3):
        frame.timestamp_ns = timestamp
        coordinator.on_stereo_frame_processed(frame)
    assert starts[0].pitcher_name == "First"
    tracker.force_end()
    assert pipeline.runtime_status().pitcher.active_name == "Second"


def test_bad_name_and_failed_finalization_do_not_change_attribution(pipeline):
    pipeline.change_pitcher("First")
    with pytest.raises(ValueError):
        pipeline.change_pitcher("  ")
    assert pipeline.runtime_status().pitcher.active_name == "First"
    pipeline._runtime.publish(recording_phase="finalizing")
    with pytest.raises(RuntimeError, match="pending stop"):
        pipeline.change_pitcher("Second")
    assert pipeline.runtime_status().pitcher.active_name == "First"


def test_roster_changes_do_not_rewrite_history_or_active_label(pipeline, tmp_path):
    pipeline.change_pitcher("First")
    artifact = tmp_path / "recordings/old/manifest.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"pitcher_name":"First"}')
    add_pitcher("First")
    with pytest.raises(ValueError, match="already exists"):
        add_pitcher("first")
    add_pitcher("Second")
    with pytest.raises(ValueError, match="already exists"):
        rename_pitcher("First", "Second")
    assert load_pitchers() == ["First", "Second"]
    rename_pitcher("First", "Renamed")
    remove_pitcher("Renamed")
    assert artifact.read_text() == '{"pitcher_name":"First"}'
    assert pipeline.runtime_status().pitcher.active_name == "First"


def test_roster_unicode_and_failed_save_preserve_existing_data(tmp_path, monkeypatch):
    from configs.pitchers import pitchers_path, save_pitchers
    save_pitchers(["山田", "José"], tmp_path)
    assert load_pitchers(tmp_path) == ["José", "山田"]
    original = pitchers_path(tmp_path).read_bytes()

    def fail_replace(*_args):
        raise OSError("Disk unavailable")

    monkeypatch.setattr("configs.pitchers.os.replace", fail_replace)
    with pytest.raises(OSError, match="Disk unavailable"):
        save_pitchers(["Next"], tmp_path)
    assert pitchers_path(tmp_path).read_bytes() == original
    assert not list(tmp_path.glob(".pitchers-*.tmp"))


def test_malformed_roster_is_not_overwritten(tmp_path):
    from configs.pitchers import pitchers_path
    roster = pitchers_path(tmp_path)
    roster.write_text('{"unexpected": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="list of pitcher names"):
        add_pitcher("Example", tmp_path)
    assert roster.read_text(encoding="utf-8") == '{"unexpected": []}'
