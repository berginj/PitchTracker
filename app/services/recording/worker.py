"""Bounded frame-I/O worker that isolates capture publishers from codecs."""

from __future__ import annotations

import queue
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordingWorkerStats:
    submitted: int
    written: int
    dropped: int
    failed: int
    queue_depth: int


class BoundedRecordingWorker:
    """FIFO worker with an explicit drop-newest overload policy."""

    def __init__(self, handler: Callable[[Any], None], *, max_queue: int = 240) -> None:
        if max_queue <= 0:
            raise ValueError("max_queue must be positive")
        self._handler = handler
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lifecycle_lock = threading.Lock()
        self._accepting = False
        self._stats_lock = threading.Lock()
        self._submitted = self._written = self._dropped = self._failed = 0

    def start(self) -> bool:
        """Start a fresh accepting generation, or report a stale live generation."""
        with self._lifecycle_lock:
            if self._thread and self._thread.is_alive():
                return self._accepting and not self._stop.is_set()
            if not self._queue.empty():
                return False
            with self._stats_lock:
                self._submitted = self._written = self._dropped = self._failed = 0
            self._stop.clear()
            self._accepting = True
            self._thread = threading.Thread(target=self._run, name="recording-frame-writer", daemon=True)
            self._thread.start()
            return True

    def submit(self, item: Any) -> bool:
        with self._lifecycle_lock:
            if not self._accepting or self._stop.is_set() or not self._thread or not self._thread.is_alive():
                with self._stats_lock:
                    self._dropped += 1
                return False
            try:
                self._queue.put_nowait(item)
                with self._stats_lock:
                    self._submitted += 1
                return True
            except queue.Full:
                with self._stats_lock:
                    self._dropped += 1
                return False

    def wait_idle(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            stats = self.stats()
            if stats.queue_depth == 0 and stats.written + stats.failed >= stats.submitted:
                return True
            time.sleep(0.01)
        return False

    def stop(self, *, drain: bool = True, timeout: float = 10.0) -> bool:
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

    def stats(self) -> RecordingWorkerStats:
        with self._stats_lock:
            return RecordingWorkerStats(
                self._submitted,
                self._written,
                self._dropped,
                self._failed,
                self._queue.qsize(),
            )

    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self._handler(item)
                with self._stats_lock:
                    self._written += 1
            except Exception:
                with self._stats_lock:
                    self._failed += 1
                logger.exception("Recording worker item failed")
            finally:
                self._queue.task_done()


__all__ = ["BoundedRecordingWorker", "RecordingWorkerStats"]
