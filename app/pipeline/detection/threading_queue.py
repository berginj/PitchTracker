"""Bounded queue management for the detection thread pool."""

import logging
import queue
import time

from app.events import ErrorCategory, ErrorSeverity, publish_error
from app.pipeline.detection.threading_items import QueuePutResult

logger = logging.getLogger(__name__)


class DetectionQueueMixin:
    """Own bounded queue reset, drop accounting, and adaptive sizing."""

    def _check_adaptive_queue_sizing(self) -> None:
        if not self._adaptive_queue_enabled:
            return

        current_time = time.monotonic()
        if current_time - self._last_adaptive_check < self._adaptive_check_interval:
            return

        with self._detection_error_lock:
            total_new_drops = 0
            for queue_name in ("left", "right"):
                drops_since_last = self._frames_dropped[queue_name] - self._frames_dropped_last_check[queue_name]
                total_new_drops += drops_since_last
                self._frames_dropped_last_check[queue_name] = self._frames_dropped[queue_name]

            old_size = self._queue_size
            if total_new_drops > 5:
                self._queue_size = min(self._queue_size + 2, self._max_queue_size)
            elif total_new_drops < 1 and self._queue_size > self._min_queue_size:
                self._queue_size = max(self._queue_size - 1, self._min_queue_size)

            self._last_adaptive_check = current_time
            if self._queue_size != old_size:
                logger.info(
                    "Adaptive queue sizing: adjusted from %s to %s " "(drops in last %ss: %s)",
                    old_size,
                    self._queue_size,
                    self._adaptive_check_interval,
                    total_new_drops,
                )

    def _reset_queues(self) -> None:
        self._left_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._right_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._detect_result_queue = queue.Queue(maxsize=self._queue_size * 4)

    def _queue_put_drop_oldest(self, target: queue.Queue, item, queue_name: str = "unknown") -> QueuePutResult:
        with self._detection_error_lock:
            self._queue_attempts[queue_name] = self._queue_attempts.get(queue_name, 0) + 1

        try:
            target.put_nowait(item)
            return QueuePutResult()
        except queue.Full:
            should_log, should_log_critical, drop_count = self._record_queue_drop(queue_name)

            if should_log:
                logger.warning(
                    "Detection queue '%s' full, dropped %s frames total. "
                    "Detection may not be keeping up with frame rate.",
                    queue_name,
                    drop_count,
                )
                publish_error(
                    category=ErrorCategory.DETECTION,
                    severity=ErrorSeverity.WARNING,
                    message=f"Detection queue '{queue_name}' full, dropping frames",
                    source=f"DetectionThreadPool.{queue_name}",
                    frames_dropped=drop_count,
                    queue_name=queue_name,
                )

            if should_log_critical:
                publish_error(
                    category=ErrorCategory.DETECTION,
                    severity=ErrorSeverity.CRITICAL,
                    message=(f"Detection queue '{queue_name}' consistently dropping " f"frames ({drop_count} total)"),
                    source=f"DetectionThreadPool.{queue_name}",
                    frames_dropped=drop_count,
                    queue_name=queue_name,
                )

        displaced = None
        try:
            displaced = target.get_nowait()
        except queue.Empty:
            pass

        try:
            target.put_nowait(item)
            return QueuePutResult(displaced=displaced)
        except queue.Full:
            logger.error(
                "Failed to put item in queue '%s' even after dropping oldest",
                queue_name,
            )
            with self._detection_error_lock:
                self._frames_dropped[queue_name] = self._frames_dropped.get(queue_name, 0) + 1
            return QueuePutResult(displaced=displaced, accepted=False)

    def _record_queue_drop(self, queue_name: str) -> tuple[bool, bool, int]:
        with self._detection_error_lock:
            self._frames_dropped[queue_name] = self._frames_dropped.get(queue_name, 0) + 1
            drop_count = self._frames_dropped[queue_name]
            current_time = time.monotonic()
            time_since_last_log = current_time - self._last_drop_log_time.get(queue_name, 0.0)
            should_log = time_since_last_log > 5.0
            if should_log:
                self._last_drop_log_time[queue_name] = current_time
            should_log_critical = drop_count >= 100 and drop_count % 100 == 0
        return should_log, should_log_critical, drop_count
