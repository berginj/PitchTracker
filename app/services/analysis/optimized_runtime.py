"""Per-job configuration snapshots, warm fitting, and deferred comparison ownership."""

from copy import deepcopy
from dataclasses import replace
import logging
from threading import Thread
from time import monotonic_ns

from app.events.trajectory_events import TrajectoryComparisonEvent, TrajectoryFitPreparedEvent
from app.events.event_metadata import make_event_metadata
from app.pipeline.analysis.pitch_summary import _compact_trajectory_result
from app.services.analysis.fit_worker import FitWorkerPool
from app.services.analysis.pitch_terminal import PitchTerminalHandler
from app.services.analysis.worker import BoundedAnalysisWorker
from contracts.fit_jobs import AnalysisJob
from trajectory.contracts import FailureCode
from app.services.analysis.fit_worker import PersistentFitWorker

logger = logging.getLogger(__name__)


class OptimizedAnalysisRuntime:
    def __init__(self, service):
        self.service = service
        self.pool = FitWorkerPool()
        self.comparison_pool = FitWorkerPool()
        self.comparisons = BoundedAnalysisWorker(self._compare, max_queue=8)
        self.warmer: Thread | None = None

    def start(self):
        self.comparisons.start()
        self.warmer = Thread(target=self._warm, name="trajectory-warmup", daemon=True)
        self.warmer.start()

    def _warm(self):
        try:
            self.pool.warm()
        except Exception:
            logger.exception("Numerical warmup failed; next request will retry")

    def stop(self):
        if not self.comparisons.stop(drain=True):
            raise RuntimeError("Trajectory comparisons are still draining; retry stop")
        self.pool.close()
        self.comparison_pool.close()
        if self.warmer is not None:
            self.warmer.join(timeout=2)

    def snapshot(self, event):
        with self.service._lock:
            modes = [self.service._config.trajectory.primary_mode, *self.service._config.trajectory.compare_modes]
            models = (
                self.service._analyzer._load_ray_camera_models()
                if any(mode.startswith("ray_") for mode in modes)
                else {}
            )
            return AnalysisJob(
                deepcopy(event),
                deepcopy(self.service._config),
                self.service._get_ball_radius(),
                self.service._manual_speed_mph,
                deepcopy(models),
                monotonic_ns(),
            )

    def analyze(self, job):
        # Accept legacy direct submissions from integrations as well.
        if not isinstance(job, AnalysisJob):
            job = self.snapshot(job)
        service = self.service

        def primary_fit(request):
            waited = (monotonic_ns() - job.submitted_ns) / 1e9 if job.submitted_ns else 0
            remaining = request.deadline_seconds - waited
            if remaining <= 0:
                return PersistentFitWorker._failure(
                    request, FailureCode.DEADLINE_EXCEEDED, "Analysis admission deadline"
                )
            return self.pool.fit(replace(request, deadline_seconds=remaining))

        analyzer = service._analyzer.for_job(
            job.config,
            lambda: job.ball_radius_in,
            lambda: job.manual_speed_mph,
            lambda: "manual_override",
            fit_runner=primary_fit,
            fit_observer=lambda pid, payload: service._event_bus.publish(
                TrajectoryFitPreparedEvent(
                    pid,
                    payload,
                    make_event_metadata(
                        "TrajectoryFitPreparedEvent",
                        correlation_id=pid,
                        pitch_id=pid,
                        session_id=service._aggregator.session_id,
                        timestamp_ns=job.event.timestamp_ns,
                    ),
                )
            ),
            defer_comparisons=True,
            camera_models_snapshot=job.camera_models,
        )
        handler = PitchTerminalHandler(
            service._event_bus,
            analyzer,
            service._aggregator,
            service._refiner,
            service._lock,
            submitted_ns=job.submitted_ns,
        )
        handler.handle_pitch_end(job.event)
        requests = analyzer.take_comparison_requests()
        if requests and not self.comparisons.submit((job.event.pitch_id, requests, service._aggregator.session_id)):
            self._publish_comparisons(
                job.event.pitch_id,
                {r.mode: {"status": "QUEUE_DROPPED"} for r in requests},
                service._aggregator.session_id,
            )

    def _compare(self, item):
        pitch_id, requests, session_id = item
        results = {}
        for request in requests:
            from trajectory.serialization import encode_request
            import json

            self.service._event_bus.publish(
                TrajectoryFitPreparedEvent(
                    pitch_id,
                    json.loads(encode_request(request)),
                    make_event_metadata(
                        "TrajectoryFitPreparedEvent",
                        correlation_id=pitch_id,
                        pitch_id=pitch_id,
                        session_id=session_id,
                        timestamp_ns=monotonic_ns(),
                    ),
                )
            )
            results[request.mode] = _compact_trajectory_result(self.comparison_pool.fit(request))
        self._publish_comparisons(pitch_id, results, session_id)

    def _publish_comparisons(self, pitch_id, results, session_id):
        self.service._event_bus.publish(
            TrajectoryComparisonEvent(
                pitch_id,
                results,
                make_event_metadata(
                    "TrajectoryComparisonEvent",
                    correlation_id=pitch_id,
                    pitch_id=pitch_id,
                    session_id=session_id,
                    timestamp_ns=monotonic_ns(),
                ),
            )
        )
