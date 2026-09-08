"""Bounded background work queue for trajectory analysis."""

from __future__ import annotations

import queue
import logging
import threading
import time
from collections.abc import Callable
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerStats:
    submitted: int
    completed: int
    dropped: int
    failed: int
    queue_depth: int
    oldest_queued_age_ms: float = 0.0
    last_queue_wait_ms: float = 0.0
    service_latency_p95_ms: float = 0.0
    latency_sample_count: int = 0


class BoundedAnalysisWorker:
    def __init__(self, handler: Callable[[Any], None], *, max_queue: int = 8) -> None:
        if max_queue <= 0:
            raise ValueError("max_queue must be positive")
        self._handler = handler
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lifecycle_lock = threading.Lock()
        self._accepting = False
        self._stats_lock = threading.Lock()
        self._submitted = self._completed = self._dropped = self._failed = 0
        self._service_latencies: deque[float] = deque(maxlen=256)
        self._last_queue_wait_ms = 0.0

    def start(self) -> bool:
        """Start a fresh accepting generation, or report a stale live generation."""
        with self._lifecycle_lock:
            if self._thread and self._thread.is_alive():
                return self._accepting and not self._stop.is_set()
            if not self._queue.empty():
                return False
            with self._stats_lock:
                self._submitted = self._completed = self._dropped = self._failed = 0
                self._service_latencies.clear()
                self._last_queue_wait_ms = 0.0
            self._stop.clear()
            self._accepting = True
            self._thread = threading.Thread(target=self._run, name="pitch-analysis-worker", daemon=True)
            self._thread.start()
            return True

    def submit(self, item: Any) -> bool:
        with self._lifecycle_lock:
            if not self._accepting or self._stop.is_set() or not self._thread or not self._thread.is_alive():
                with self._stats_lock:
                    self._dropped += 1
                return False
            try:
                self._queue.put_nowait((time.monotonic(), item))
                with self._stats_lock:
                    self._submitted += 1
                return True
            except queue.Full:
                with self._stats_lock:
                    self._dropped += 1
                return False

    def stop(self, *, drain: bool = True, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._lifecycle_lock:
            self._accepting = False
        drained = self.wait_idle(max(0.0, deadline - time.monotonic())) if drain else True
        self._stop.set()
        with self._lifecycle_lock:
            thread = self._thread
        if thread:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        stopped = thread is None or not thread.is_alive()
        if stopped:
            with self._lifecycle_lock:
                if self._thread is thread:
                    self._thread = None
        return drained and stopped

    def stats(self) -> WorkerStats:
        with self._queue.mutex:
            depth = len(self._queue.queue)
            oldest = self._queue.queue[0][0] if depth else None
        with self._stats_lock:
            latencies = sorted(self._service_latencies)
            p95 = latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)] if latencies else 0.0
            return WorkerStats(
                self._submitted,
                self._completed,
                self._dropped,
                self._failed,
                depth,
                max(0.0, (time.monotonic() - oldest) * 1000) if oldest is not None else 0.0,
                self._last_queue_wait_ms,
                p95,
                len(latencies),
            )

    def wait_idle(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            stats = self.stats()
            if stats.queue_depth == 0 and stats.completed + stats.failed >= stats.submitted:
                return True
            time.sleep(0.01)
        return False

    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                queued_at, item = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            started = time.monotonic()
            with self._stats_lock:
                self._last_queue_wait_ms = (started - queued_at) * 1000
            try:
                self._handler(item)
                with self._stats_lock:
                    self._completed += 1
            except Exception:
                with self._stats_lock:
                    self._failed += 1
                logger.exception("Analysis worker item failed")
            finally:
                with self._stats_lock:
                    self._service_latencies.append((time.monotonic() - started) * 1000)
                self._queue.task_done()


__all__ = ["BoundedAnalysisWorker", "WorkerStats"]
