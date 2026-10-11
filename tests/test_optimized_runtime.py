"""Frozen job inputs and primary-before-comparison publication."""

from dataclasses import replace
from pathlib import Path
from threading import Event

from app.events.event_bus import EventBus
from app.events.event_types import PitchAnalyzedEvent, PitchEndEvent
from app.events.trajectory_events import TrajectoryComparisonEvent
from app.services.analysis.implementation import AnalysisServiceImpl
from configs.settings import load_config
from trajectory.contracts import FailureCode, TrajectoryDiagnostics, TrajectoryFitResult
from trajectory.physics import PhysicsDragFitter
from trajectory.sim import SimConfig, simulate_ballistic


def test_primary_publishes_while_comparison_is_still_busy(monkeypatch):
    config = load_config(Path("configs/default.yaml"))
    config = replace(config, trajectory=replace(config.trajectory, compare_modes=["ray_graph"]))
    bus = EventBus()
    service = AnalysisServiceImpl(bus, config)
    primary, comparisons = [], []
    bus.subscribe(PitchAnalyzedEvent, primary.append)
    bus.subscribe(TrajectoryComparisonEvent, comparisons.append)
    entered, release = Event(), Event()
    service.start_analysis("session")
    monkeypatch.setattr(service._fit_runtime.pool, "fit", PhysicsDragFitter().fit_trajectory)

    def compare(request):
        entered.set()
        assert release.wait(5)
        return TrajectoryFitResult(
            request.mode,
            [],
            None,
            None,
            None,
            0,
            TrajectoryDiagnostics(failure_codes=[FailureCode.CAMERA_MODEL_MISSING]),
        )

    monkeypatch.setattr(service._fit_runtime.comparison_pool, "fit", compare)
    observations = simulate_ballistic(SimConfig(outlier_prob=0, noise_ft=0.01))
    event = PitchEndEvent("pitch_1", observations, observations[-1].t_ns, observations[-1].t_ns)
    try:
        job = service._fit_runtime.snapshot(event)
        service._config = replace(config, trajectory=replace(config.trajectory, compute_backend="reference"))
        assert job.config.trajectory.compute_backend == "cpu"
        assert job.event.observations is not event.observations
        service._analysis_worker.submit(job)
        assert entered.wait(5)
        assert len(primary) == 1 and not comparisons
        assert primary[0].summary.trajectory_comparison["ray_graph"]["status"] == "DEFERRED"
        assert "queue_and_analysis_ms" in primary[0].summary.quality_diagnostics
        release.set()
        assert service._fit_runtime.comparisons.wait_idle(5)
        assert comparisons[0].pitch_id == "pitch_1"
        assert len(primary) == 1
    finally:
        release.set()
        service.stop_analysis()
