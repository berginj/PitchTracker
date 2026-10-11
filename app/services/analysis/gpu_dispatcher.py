"""Bounded GPU batching outside the capture/UI process, with hard deadlines."""

from collections import deque
from concurrent.futures import CancelledError, Future, TimeoutError as FutureTimeout
from dataclasses import dataclass, replace
import logging
import queue
from threading import Event, Thread
from time import monotonic

from app.services.analysis.fit_worker import Cancellation, PersistentFitWorker
from trajectory.contracts import FailureCode, TrajectoryFitRequest, TrajectoryFitResult

logger = logging.getLogger(__name__)


@dataclass
class GPUJob:
    request: TrajectoryFitRequest
    deadline: float
    future: Future[TrajectoryFitResult]
    cancel: Cancellation


class GPUFitDispatcher:
    def __init__(self, count):
        self.count = count
        self.pending: queue.Queue[GPUJob] = queue.Queue(maxsize=count)
        self.closed = Event()
        self.worker = PersistentFitWorker()
        self.thread = Thread(target=self._run, name="gpu-fit-dispatch", daemon=True)
        self.thread.start()

    def fit(self, request: TrajectoryFitRequest, cancel: Cancellation) -> TrajectoryFitResult:
        job = GPUJob(request, monotonic() + request.deadline_seconds, Future(), cancel)
        while True:
            if cancel.is_set():
                raise CancelledError()
            if self.closed.is_set():
                return PersistentFitWorker._failure(request, FailureCode.OPT_DID_NOT_CONVERGE, "GPU dispatcher stopped")
            remaining = job.deadline - monotonic()
            if remaining <= 0:
                return self._timeout(job)
            try:
                self.pending.put(job, timeout=min(remaining, 0.05))
                break
            except queue.Full:
                continue
        while True:
            if cancel.is_set():
                raise CancelledError()
            if self.closed.is_set():
                return PersistentFitWorker._failure(request, FailureCode.OPT_DID_NOT_CONVERGE, "GPU dispatcher stopped")
            remaining = job.deadline - monotonic()
            if remaining <= 0:
                return self._timeout(job)
            try:
                return job.future.result(timeout=min(remaining, 0.05))
            except FutureTimeout:
                continue

    @staticmethod
    def _timeout(job) -> TrajectoryFitResult:
        return PersistentFitWorker._failure(job.request, FailureCode.DEADLINE_EXCEEDED, "GPU batch admission deadline")

    @staticmethod
    def _key(job):
        request = job.request
        return (
            len(request.observations),
            request.drag_prior_enabled,
            request.drag_k0,
            max(request.drag_sigma, 1e-6),
            request.compute_backend,
        )

    def _run(self):
        deferred: deque[GPUJob] = deque()
        try:
            while not self.closed.is_set():
                try:
                    first = deferred.popleft() if deferred else self.pending.get(timeout=0.05)
                except queue.Empty:
                    continue
                group = [first]
                deadline = monotonic() + 0.002
                while len(group) < self.count and monotonic() < deadline:
                    try:
                        job = self.pending.get(timeout=max(deadline - monotonic(), 0.00001))
                    except queue.Empty:
                        break
                    if self._key(job) == self._key(first):
                        group.append(job)
                    else:
                        deferred.append(job)
                active = []
                for job in group:
                    if job.cancel.is_set():
                        job.future.set_exception(CancelledError())
                    elif job.deadline <= monotonic():
                        job.future.set_result(self._timeout(job))
                    else:
                        active.append(job)
                if not active:
                    continue
                requests = [
                    replace(
                        job.request,
                        deadline_seconds=max(1e-9, job.deadline - monotonic()),
                        compute_concurrency=len(active),
                    )
                    for job in active
                ]
                try:
                    results = self.worker.fit_batch(
                        requests, Cancellation(self.closed, *(job.cancel for job in active))
                    )
                except CancelledError:
                    results = [None] * len(active)
                for job, result in zip(active, results):
                    if job.cancel.is_set() or self.closed.is_set():
                        job.future.set_exception(CancelledError())
                        continue
                    # Worker failure can degrade within the caller's remaining budget.
                    retry = result is None or any(
                        code in {FailureCode.INVALID_INPUT, FailureCode.DEADLINE_EXCEEDED}
                        for code in result.diagnostics.failure_codes
                    )
                    if retry and job.deadline > monotonic():
                        try:
                            result = self.worker.fit(
                                replace(
                                    job.request,
                                    compute_backend="cpu",
                                    deadline_seconds=max(1e-9, job.deadline - monotonic()),
                                ),
                                Cancellation(job.cancel, self.closed),
                            )
                            result.diagnostics.performance.update(
                                requested_backend=job.request.compute_backend,
                                fallback_reason="Shared GPU worker failed",
                            )
                        except CancelledError:
                            job.future.set_exception(CancelledError())
                            continue
                    job.future.set_result(result or self._timeout(job))
        except Exception:
            logger.exception("GPU dispatcher failed")
            self.closed.set()
        finally:
            for job in deferred:
                job.future.set_exception(CancelledError())
            while not self.pending.empty():
                self.pending.get_nowait().future.set_exception(CancelledError())
            self.worker.close()

    def close(self):
        self.closed.set()
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            raise RuntimeError("GPU dispatcher is still stopping; retry shutdown")
