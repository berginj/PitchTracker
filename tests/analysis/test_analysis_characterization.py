"""Characterization tests for the AnalysisService refactoring.

Covers: success path, expected fit failure, queue drop, duplicate pitch,
session aggregation, stop drain, and refinement failure.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.events.event_bus import EventBus
from app.events.event_types import PitchAnalyzedEvent, PitchEndEvent
from app.services.analysis import AnalysisServiceImpl
from configs.settings import load_config
from contracts import StereoObservation


def _config():
    return load_config(Path(__file__).parents[2] / "configs" / "default.yaml")


def _obs(t_ns: int = 1_000_000_000) -> StereoObservation:
    return StereoObservation(
        t_ns=t_ns, left=(100.0, 100.0), right=(110.0, 100.0),
        X=0.0, Y=3.5, Z=50.0, quality=0.9, confidence=0.9,
    )


def _event(pitch_id: str, obs_count: int = 15) -> PitchEndEvent:
    base_ns = 1_000_000_000
    obs = [_obs(base_ns + i * 30_000_000) for i in range(obs_count)]
    return PitchEndEvent(
        pitch_id=pitch_id,
        observations=obs,
        timestamp_ns=base_ns + obs_count * 30_000_000,
        duration_ns=obs_count * 30_000_000,
    )


class TestSuccessPath:
    """Successful pitch analysis produces a terminal event with session summary."""

    def test_success_publishes_analyzed_event(self):
        bus = EventBus()
        results = []
        bus.subscribe(PitchAnalyzedEvent, results.append)
        svc = AnalysisServiceImpl(bus, _config())
        svc.start_analysis()
        try:
            bus.publish(_event("pitch_00001"))
            assert svc.wait_for_idle(5.0)
            assert len(results) == 1
            assert results[0].pitch_id == "pitch_00001"
            assert results[0].session_summary.pitch_count == 1
        finally:
            svc.stop_analysis()

    def test_session_summary_accumulates(self):
        bus = EventBus()
        svc = AnalysisServiceImpl(bus, _config())
        svc.start_analysis()
        try:
            bus.publish(_event("pitch_00001"))
            bus.publish(_event("pitch_00002"))
            assert svc.wait_for_idle(5.0)
            summary = svc.get_session_summary()
            assert summary.pitch_count == 2
        finally:
            svc.stop_analysis()


class TestExpectedFitFailure:
    """When trajectory fitting fails, an UNAVAILABLE verdict is still published."""

    def test_fit_failure_publishes_unavailable(self):
        bus = EventBus()
        results = []
        bus.subscribe(PitchAnalyzedEvent, results.append)
        svc = AnalysisServiceImpl(bus, _config())
        svc.start_analysis()
        try:
            with patch.object(
                svc._analyzer, "analyze_pitch", side_effect=ValueError("fit diverged")
            ):
                bus.publish(_event("pitch_fail"))
                assert svc.wait_for_idle(5.0)
            assert len(results) == 1
            assert results[0].summary.measurement_status == "UNAVAILABLE"
            assert "ANALYSIS_PIPELINE_EXCEPTION" in results[0].summary.quality_diagnostics["reason_codes"]
            stats = svc.get_worker_stats()
            assert stats["failed"] == 1
        finally:
            svc.stop_analysis()


class TestQueueDrop:
    """When the worker queue is full, a drop verdict is published immediately."""

    def test_queue_full_publishes_drop(self):
        bus = EventBus()
        results = []
        bus.subscribe(PitchAnalyzedEvent, results.append)
        config = _config()
        svc = AnalysisServiceImpl(bus, config)
        # Use tiny queue
        from app.services.analysis.worker import BoundedAnalysisWorker
        svc._analysis_worker = BoundedAnalysisWorker(
            svc._terminal_handler.handle_pitch_end, max_queue=1
        )
        svc.start_analysis()
        try:
            # Block the worker with a slow handler
            import threading
            block = threading.Event()
            original = svc._terminal_handler.handle_pitch_end

            def slow_handler(event):
                block.wait(timeout=5)
                original(event)

            svc._analysis_worker._handler = slow_handler

            # First fills the single slot, second should drop
            bus.publish(_event("pitch_block"))
            import time
            time.sleep(0.05)
            bus.publish(_event("pitch_queued"))
            time.sleep(0.05)
            bus.publish(_event("pitch_dropped"))
            time.sleep(0.1)

            # The dropped pitch should have a terminal event already
            dropped = [r for r in results if r.pitch_id == "pitch_dropped"]
            assert len(dropped) == 1
            assert "ANALYSIS_QUEUE_DROPPED" in dropped[0].summary.quality_diagnostics["reason_codes"]

            block.set()
        finally:
            svc.stop_analysis()


class TestDuplicatePitch:
    """A pitch_id that already has a terminal result is ignored."""

    def test_duplicate_ignored(self):
        bus = EventBus()
        results = []
        bus.subscribe(PitchAnalyzedEvent, results.append)
        svc = AnalysisServiceImpl(bus, _config())
        svc.start_analysis()
        try:
            bus.publish(_event("pitch_dup"))
            assert svc.wait_for_idle(5.0)
            # Manually re-submit the same pitch_id
            bus.publish(_event("pitch_dup"))
            assert svc.wait_for_idle(5.0)
            # Only one terminal event
            dup_results = [r for r in results if r.pitch_id == "pitch_dup"]
            assert len(dup_results) == 1
            assert svc.get_session_summary().pitch_count == 1
        finally:
            svc.stop_analysis()


class TestSessionAggregation:
    """Heatmap and strike/ball counters update correctly."""

    def test_heatmap_initial_zeros(self):
        bus = EventBus()
        svc = AnalysisServiceImpl(bus, _config())
        svc.start_analysis()
        try:
            summary = svc.get_session_summary()
            assert summary.heatmap == [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        finally:
            svc.stop_analysis()


class TestStopDrain:
    """stop_analysis drains queued work before returning."""

    def test_drain_completes_pending(self):
        bus = EventBus()
        results = []
        bus.subscribe(PitchAnalyzedEvent, results.append)
        svc = AnalysisServiceImpl(bus, _config())
        svc.start_analysis()
        bus.publish(_event("pitch_drain"))
        svc.stop_analysis()
        # After stop, the event should have been processed
        assert len(results) == 1
        assert results[0].pitch_id == "pitch_drain"


class TestRefinementFailure:
    """Refinement failure does not produce a second terminal event."""

    def test_refinement_error_no_second_event(self):
        bus = EventBus()
        results = []
        bus.subscribe(PitchAnalyzedEvent, results.append)
        config = _config()
        svc = AnalysisServiceImpl(bus, config)
        # Force refinement enabled and mock refiner to raise
        svc._refiner._enabled = True
        svc._refiner._refiner = MagicMock()
        svc._refiner._refiner.accumulate_trajectory.side_effect = RuntimeError("refiner broken")
        svc.start_analysis()
        try:
            bus.publish(_event("pitch_ref"))
            assert svc.wait_for_idle(5.0)
            # Only one terminal event despite refinement failure
            ref_results = [r for r in results if r.pitch_id == "pitch_ref"]
            assert len(ref_results) == 1
            stats = svc.get_worker_stats()
            # Worker should not count refinement failure as a worker failure
            assert stats["failed"] == 0
        finally:
            svc.stop_analysis()
