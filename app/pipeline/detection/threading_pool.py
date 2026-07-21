"""Detection threading pool for managing detection workers and stereo matching."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from app.events import ErrorCategory, ErrorSeverity, publish_error
from app.events.event_types import FrameProcessingOpportunityEvent, FrameProcessingOutcomeEvent
from app.pipeline.detection.decision_ids import frame_decision_id
from contracts import Detection, Frame

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _FrameWorkItem:
    opportunity_id: str
    label: str
    frame: Frame


@dataclass(frozen=True)
class _DetectionResultItem:
    work: _FrameWorkItem
    detections: list[Detection]


@dataclass(frozen=True)
class _QueuePutResult:
    displaced: object | None = None
    accepted: bool = True


class DetectionThreadPool:
    """Manages detection threading with configurable worker modes.

    Supports two threading modes:
    - per_camera: One dedicated thread per camera
    - worker_pool: Shared pool of workers processing both cameras

    Handles:
    - Frame queuing for detection
    - Detection worker threads
    - Stereo matching thread
    - Result aggregation
    """

    def __init__(self, mode: str = "per_camera", worker_count: int = 2):
        """Initialize detection thread pool.

        Args:
            mode: Threading mode ("per_camera" or "worker_pool")
            worker_count: Number of worker threads for worker_pool mode
        """
        self._mode = mode
        self._worker_count = worker_count

        # Queues
        self._left_detect_queue: queue.Queue[_FrameWorkItem] = queue.Queue()
        self._right_detect_queue: queue.Queue[_FrameWorkItem] = queue.Queue()
        self._detect_result_queue: queue.Queue[_DetectionResultItem] = queue.Queue()
        self._queue_size = 6

        # Threading state
        self._detection_running = False
        self._detector_threads: List[threading.Thread] = []
        self._worker_threads: List[threading.Thread] = []
        self._stereo_thread: Optional[threading.Thread] = None

        # Worker pool state
        self._detector_busy: Dict[str, bool] = {"left": False, "right": False}
        self._detector_busy_lock = threading.Lock()

        # Callbacks
        self._detect_callback: Optional[Callable[[str, Frame], list[Detection]]] = None
        self._stereo_callback: Optional[Callable[[str, Frame, list[Detection]], None]] = None
        self._error_callback: Optional[Callable[[str, Exception], None]] = None
        self._frame_opportunity_callback: Optional[Callable[[FrameProcessingOpportunityEvent], None]] = None
        self._frame_outcome_callback: Optional[Callable[[FrameProcessingOutcomeEvent], None]] = None

        # Error tracking
        self._detection_errors: Dict[str, int] = {"left": 0, "right": 0}
        self._detection_error_lock = threading.Lock()
        self._last_error_log_time: Dict[str, float] = {"left": 0.0, "right": 0.0}
        self._max_consecutive_errors = 10

        # Cumulative, opportunity-based processing counters.  These are kept
        # separately from _detection_errors because that counter intentionally
        # resets after recovery and therefore cannot support an error rate.
        self._processing_attempts: Dict[str, int] = {"left": 0, "right": 0, "results": 0}
        self._processing_failures: Dict[str, int] = {"left": 0, "right": 0, "results": 0}

        # Frame drop tracking
        self._frames_dropped: Dict[str, int] = {"left": 0, "right": 0, "results": 0}
        self._queue_attempts: Dict[str, int] = {"left": 0, "right": 0, "results": 0}
        self._last_drop_log_time: Dict[str, float] = {"left": 0.0, "right": 0.0, "results": 0.0}
        self._drop_warning_threshold = 10  # Warn after this many drops

        # Per-frame conservation state. Each offered work item remains open until
        # one terminal result is emitted, including stop-time cancellation.
        self._opportunity_sequence = 0
        self._run_epoch = 0
        self._open_opportunities: Dict[str, _FrameWorkItem] = {}
        self._terminal_opportunities: set[str] = set()
        self._terminal_outcomes: Counter[str] = Counter()

        # Adaptive queue sizing
        self._adaptive_queue_enabled = True
        self._min_queue_size = 3
        self._max_queue_size = 12
        self._last_adaptive_check = 0.0
        self._adaptive_check_interval = 10.0  # Check every 10 seconds
        self._frames_dropped_last_check: Dict[str, int] = {"left": 0, "right": 0, "results": 0}

    def set_detect_callback(self, callback: Callable[[str, Frame], list[Detection]]) -> None:
        """Set callback for detection.

        Args:
            callback: Function to detect frame, receives (label, frame), returns list[Detection]
        """
        self._detect_callback = callback

    def set_stereo_callback(self, callback: Callable[[str, Frame, list[Detection]], None]) -> None:
        """Set callback for stereo processing.

        Args:
            callback: Function to process stereo result, receives (label, frame, detections)
        """
        self._stereo_callback = callback

    def set_error_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """Set callback for error notification.

        Args:
            callback: Function to handle errors, receives (source, exception)
        """
        self._error_callback = callback

    def set_frame_decision_callbacks(
        self,
        opportunity_callback: Callable[[FrameProcessingOpportunityEvent], None],
        outcome_callback: Callable[[FrameProcessingOutcomeEvent], None],
    ) -> None:
        """Register non-blocking publishers for replayable frame decisions."""

        self._frame_opportunity_callback = opportunity_callback
        self._frame_outcome_callback = outcome_callback

    def start(self, queue_size: int = 6) -> None:
        """Start detection threads.

        Args:
            queue_size: Maximum queue depth for detection frames
        """
        if self._detection_running:
            return

        self._queue_size = queue_size
        self._reset_queues()
        self._detection_running = True
        self._run_epoch += 1
        self._detector_busy = {"left": False, "right": False}
        self._detector_threads = []
        self._worker_threads = []

        # Reset error tracking
        with self._detection_error_lock:
            self._detection_errors = {"left": 0, "right": 0}
            self._last_error_log_time = {"left": 0.0, "right": 0.0}
            self._processing_attempts = {"left": 0, "right": 0, "results": 0}
            self._processing_failures = {"left": 0, "right": 0, "results": 0}
            self._frames_dropped = {"left": 0, "right": 0, "results": 0}
            self._queue_attempts = {"left": 0, "right": 0, "results": 0}
            self._frames_dropped_last_check = {"left": 0, "right": 0, "results": 0}
            self._last_drop_log_time = {"left": 0.0, "right": 0.0, "results": 0.0}
            self._opportunity_sequence = 0
            self._open_opportunities.clear()
            self._terminal_opportunities.clear()
            self._terminal_outcomes.clear()

        # Start stereo matching thread
        self._stereo_thread = threading.Thread(target=self._stereo_loop, daemon=True)
        self._stereo_thread.start()

        # Start detection threads based on mode
        if self._mode == "per_camera":
            self._detector_threads = [
                threading.Thread(
                    target=self._detection_loop_per_camera,
                    args=("left", self._left_detect_queue),
                    daemon=True,
                ),
                threading.Thread(
                    target=self._detection_loop_per_camera,
                    args=("right", self._right_detect_queue),
                    daemon=True,
                ),
            ]
            for thread in self._detector_threads:
                thread.start()
        else:
            # worker_pool mode
            for _ in range(max(1, self._worker_count)):
                thread = threading.Thread(target=self._detection_loop_pool, daemon=True)
                self._worker_threads.append(thread)
                thread.start()

    def stop(self) -> None:
        """Stop all detection threads."""
        self._detection_running = False

        for thread in self._detector_threads:
            thread.join(timeout=1.0)
        for thread in self._worker_threads:
            thread.join(timeout=1.0)
        if self._stereo_thread is not None:
            self._stereo_thread.join(timeout=1.0)

        # A driver/detector callback can outlive the bounded join. Close every
        # remaining opportunity exactly once; a late callback is de-duplicated.
        with self._detection_error_lock:
            remaining = list(self._open_opportunities.values())
        for work in remaining:
            self._finish_opportunity(work, "CANCELLED_ON_STOP", reason_codes=("POOL_STOPPED",))

        self._detector_threads = []
        self._worker_threads = []
        self._stereo_thread = None

    def enqueue_frame(self, label: str, frame: Frame) -> None:
        """Enqueue frame for detection.

        Args:
            label: Camera label ("left" or "right")
            frame: Frame to detect
        """
        if not self._detection_running:
            return

        target = self._left_detect_queue if label == "left" else self._right_detect_queue
        with self._detection_error_lock:
            self._opportunity_sequence += 1
            opportunity_id = (
                f"detection:{self._run_epoch}:{self._opportunity_sequence}:{frame_decision_id(frame)}"
            )
            work = _FrameWorkItem(opportunity_id, label, frame)
            self._open_opportunities[opportunity_id] = work
        self._publish_opportunity(work)
        result = self._queue_put_drop_oldest(target, work, queue_name=label)
        if isinstance(result.displaced, _FrameWorkItem):
            self._finish_opportunity(
                result.displaced,
                "INPUT_QUEUE_DROPPED",
                reason_codes=("DROP_OLDEST",),
            )
        if not result.accepted:
            self._finish_opportunity(work, "INPUT_QUEUE_DROPPED", reason_codes=("QUEUE_RETRY_FAILED",))

    def set_mode(self, mode: str, worker_count: int) -> None:
        """Update threading mode (requires restart to take effect).

        Args:
            mode: Threading mode ("per_camera" or "worker_pool")
            worker_count: Number of worker threads for worker_pool mode
        """
        if mode not in ("per_camera", "worker_pool"):
            raise ValueError(f"Unknown detection threading mode: {mode}")
        self._mode = mode
        self._worker_count = max(1, int(worker_count))

    def is_running(self) -> bool:
        """Check if detection threads are running.

        Returns:
            True if running, False otherwise
        """
        return self._detection_running

    def get_error_stats(self) -> Dict[str, int]:
        """Get detection error statistics.

        Returns:
            Dictionary with error counts per camera {"left": count, "right": count}
        """
        with self._detection_error_lock:
            return self._detection_errors.copy()

    def get_runtime_stats(self) -> dict:
        """Return cumulative processing and queue-loss evidence.

        Every rate carries its numerator and opportunity denominator.  A
        zero-opportunity rate is ``None`` rather than a misleading zero.
        Counters reset when the pool starts and do not reset on recovery.
        """
        with self._detection_error_lock:
            attempts = self._processing_attempts.copy()
            failures = self._processing_failures.copy()
            queue_attempts = self._queue_attempts.copy()
            queue_drops = self._frames_dropped.copy()
            offered = self._opportunity_sequence
            terminal = len(self._terminal_opportunities)
            outstanding = len(self._open_opportunities)
            terminal_outcomes = dict(self._terminal_outcomes)

        stages = {
            name: {
                "attempts": attempts.get(name, 0),
                "failures": failures.get(name, 0),
                "queue_attempts": queue_attempts.get(name, 0),
                "queue_drops": queue_drops.get(name, 0),
                "failure_rate": _rate_payload(failures.get(name, 0), attempts.get(name, 0)),
                "queue_drop_rate": _rate_payload(queue_drops.get(name, 0), queue_attempts.get(name, 0)),
            }
            for name in ("left", "right", "results")
        }
        stages["frame_conservation"] = {
            "offered": offered,
            "terminal": terminal,
            "outstanding": outstanding,
            "balanced": offered == terminal + outstanding,
            "terminal_outcomes": terminal_outcomes,
        }
        return stages

    def _check_adaptive_queue_sizing(self) -> None:
        """Check and adjust queue sizes based on drop patterns.

        Increases queue size if drops are frequent, decreases if underutilized.
        Called periodically from detection loops for dynamic optimization.
        """
        if not self._adaptive_queue_enabled:
            return

        current_time = time.monotonic()
        if current_time - self._last_adaptive_check < self._adaptive_check_interval:
            return

        with self._detection_error_lock:
            # Calculate drop rate since last check
            total_new_drops = 0
            for queue_name in ("left", "right"):
                drops_since_last = self._frames_dropped[queue_name] - self._frames_dropped_last_check[queue_name]
                total_new_drops += drops_since_last
                self._frames_dropped_last_check[queue_name] = self._frames_dropped[queue_name]

            # Adjust queue size based on drop rate
            # High drops (>5 per interval): increase queue size
            # Low drops (<1 per interval): decrease queue size
            old_size = self._queue_size

            if total_new_drops > 5:
                # Increase queue size (up to max)
                self._queue_size = min(self._queue_size + 2, self._max_queue_size)
            elif total_new_drops < 1 and self._queue_size > self._min_queue_size:
                # Decrease queue size (down to min)
                self._queue_size = max(self._queue_size - 1, self._min_queue_size)

            self._last_adaptive_check = current_time

            # Log adjustment
            if self._queue_size != old_size:
                logger.info(
                    f"Adaptive queue sizing: adjusted from {old_size} to {self._queue_size} "
                    f"(drops in last {self._adaptive_check_interval}s: {total_new_drops})"
                )

                # Note: Queue size adjustment takes effect on next start()
                # Existing queues are not resized dynamically to avoid complexity

    def _reset_queues(self) -> None:
        """Reset all detection queues."""
        self._left_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._right_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._detect_result_queue = queue.Queue(maxsize=self._queue_size * 4)

    def _queue_put_drop_oldest(self, target: queue.Queue, item, queue_name: str = "unknown") -> _QueuePutResult:
        """Put item in queue, dropping oldest if full.

        Optimized to minimize lock contention by releasing lock before I/O operations.

        Args:
            target: Queue to put item in
            item: Item to put
            queue_name: Name of queue for tracking/logging
        """
        with self._detection_error_lock:
            self._queue_attempts[queue_name] = self._queue_attempts.get(queue_name, 0) + 1

        try:
            target.put_nowait(item)
            return _QueuePutResult()
        except queue.Full:
            # Minimize critical section - only lock during counter update
            should_log = False
            should_log_critical = False
            drop_count = 0

            with self._detection_error_lock:
                self._frames_dropped[queue_name] = self._frames_dropped.get(queue_name, 0) + 1
                drop_count = self._frames_dropped[queue_name]

                # Check if we should log (once per 5 seconds)
                current_time = time.monotonic()
                time_since_last_log = current_time - self._last_drop_log_time.get(queue_name, 0.0)

                if time_since_last_log > 5.0:
                    should_log = True
                    self._last_drop_log_time[queue_name] = current_time

                # Check if we should log critical error
                if drop_count >= 100 and drop_count % 100 == 0:
                    should_log_critical = True

            # Release lock before I/O operations (logging, publish_error)
            if should_log:
                logger.warning(
                    f"Detection queue '{queue_name}' full, dropped {drop_count} frames total. "
                    f"Detection may not be keeping up with frame rate."
                )

                # Publish warning event (outside lock)
                publish_error(
                    category=ErrorCategory.DETECTION,
                    severity=ErrorSeverity.WARNING,
                    message=f"Detection queue '{queue_name}' full, dropping frames",
                    source=f"DetectionThreadPool.{queue_name}",
                    frames_dropped=drop_count,
                    queue_name=queue_name,
                )

            # Publish critical error if too many drops (outside lock)
            if should_log_critical:
                publish_error(
                    category=ErrorCategory.DETECTION,
                    severity=ErrorSeverity.CRITICAL,
                    message=f"Detection queue '{queue_name}' consistently dropping frames ({drop_count} total)",
                    source=f"DetectionThreadPool.{queue_name}",
                    frames_dropped=drop_count,
                    queue_name=queue_name,
                )

        # Drop oldest item
        displaced = None
        try:
            displaced = target.get_nowait()
        except queue.Empty:
            pass

        # Try again
        try:
            target.put_nowait(item)
            return _QueuePutResult(displaced=displaced)
        except queue.Full:
            logger.error(f"Failed to put item in queue '{queue_name}' even after dropping oldest")
            with self._detection_error_lock:
                self._frames_dropped[queue_name] = self._frames_dropped.get(queue_name, 0) + 1
            return _QueuePutResult(displaced=displaced, accepted=False)

    def _detect_frame(self, label: str, frame: Frame) -> Optional[list[Detection]]:
        """Detect frame using callback.

        Args:
            label: Camera label
            frame: Frame to detect

        Returns:
            List of detections

        Note:
            Tracks detection errors and invokes error callback if too many failures.
            Throttles error logging to avoid log spam (max once per 5 seconds per camera).
        """
        try:
            with self._detection_error_lock:
                self._processing_attempts[label] = self._processing_attempts.get(label, 0) + 1
            if self._detect_callback is None:
                raise RuntimeError("Detection callback is not configured")
            detections = self._detect_callback(label, frame)

            # Success - reset error counter for this camera
            with self._detection_error_lock:
                if self._detection_errors[label] > 0:
                    logger.info(f"Detection recovered for {label} camera after {self._detection_errors[label]} errors")
                    self._detection_errors[label] = 0

            return detections

        except Exception as e:
            # Minimize critical section - only lock during counter update
            should_log = False
            should_log_critical = False
            error_count = 0

            with self._detection_error_lock:
                self._detection_errors[label] += 1
                self._processing_failures[label] = self._processing_failures.get(label, 0) + 1
                error_count = self._detection_errors[label]

                # Check if we should log (once per 5 seconds)
                current_time = time.monotonic()
                time_since_last_log = current_time - self._last_error_log_time.get(label, 0.0)

                if time_since_last_log > 5.0:
                    should_log = True
                    self._last_error_log_time[label] = current_time

                # Check if we should log critical error
                if error_count >= self._max_consecutive_errors:
                    should_log_critical = True

            # Release lock before I/O operations
            if should_log:
                logger.error(
                    f"Detection failed for {label} camera (error #{error_count}): {e.__class__.__name__}: {e}",
                    exc_info=True,
                )

                # Publish error event to bus (outside lock)
                publish_error(
                    category=ErrorCategory.DETECTION,
                    severity=ErrorSeverity.ERROR,
                    message=f"Detection failed for {label} camera",
                    source=f"DetectionThreadPool.{label}",
                    exception=e,
                    error_count=error_count,
                    camera=label,
                )

            # Notify error callback if too many consecutive failures (outside lock)
            if should_log_critical:
                logger.critical(
                    f"Detection failing consistently for {label} camera "
                    f"({error_count} consecutive errors). Detection may be broken."
                )

                # Publish critical error event
                publish_error(
                    category=ErrorCategory.DETECTION,
                    severity=ErrorSeverity.CRITICAL,
                    message=f"Detection failing consistently for {label} camera ({error_count} consecutive errors)",
                    source=f"DetectionThreadPool.{label}",
                    exception=e,
                    error_count=error_count,
                    camera=label,
                )

                if self._error_callback:
                    try:
                        self._error_callback(f"detection_{label}", e)
                    except Exception as callback_error:
                        logger.error(f"Error callback failed: {callback_error}")

            # A failed attempt is not an empty detection result.  Returning a
            # sentinel keeps it out of stereo pairing, where it would otherwise
            # be misclassified as NO_CANDIDATES.
            return None

    def _detection_loop_per_camera(self, label: str, source: queue.Queue) -> None:
        """Detection loop for per-camera mode (one thread per camera).

        Args:
            label: Camera label ("left" or "right")
            source: Queue to read frames from
        """
        while self._detection_running:
            try:
                work = source.get(timeout=0.2)
            except queue.Empty:
                continue

            detections = self._detect_frame(label, work.frame)
            if detections is not None:
                result = self._queue_put_drop_oldest(
                    self._detect_result_queue,
                    _DetectionResultItem(work, detections),
                    queue_name="results",
                )
                if isinstance(result.displaced, _DetectionResultItem):
                    self._finish_opportunity(
                        result.displaced.work,
                        "RESULT_QUEUE_DROPPED",
                        detections=result.displaced.detections,
                        reason_codes=("DROP_OLDEST",),
                    )
                if not result.accepted:
                    self._finish_opportunity(
                        work,
                        "RESULT_QUEUE_DROPPED",
                        detections=detections,
                        reason_codes=("QUEUE_RETRY_FAILED",),
                    )
            else:
                self._finish_opportunity(work, "DETECTOR_FAILED", reason_codes=("DETECTOR_EXCEPTION",))

    def _detection_loop_pool(self) -> None:
        """Detection loop for worker pool mode (shared workers)."""
        while self._detection_running:
            handled = False

            for label in ("left", "right"):
                if not self._detection_running:
                    return

                # Check if this camera is busy
                with self._detector_busy_lock:
                    if self._detector_busy.get(label, False):
                        continue

                    source = self._left_detect_queue if label == "left" else self._right_detect_queue
                    try:
                        work = source.get_nowait()
                    except queue.Empty:
                        continue

                    self._detector_busy[label] = True

                # Process frame
                detections = self._detect_frame(label, work.frame)
                if detections is not None:
                    result = self._queue_put_drop_oldest(
                        self._detect_result_queue,
                        _DetectionResultItem(work, detections),
                        queue_name="results",
                    )
                    if isinstance(result.displaced, _DetectionResultItem):
                        self._finish_opportunity(
                            result.displaced.work,
                            "RESULT_QUEUE_DROPPED",
                            detections=result.displaced.detections,
                            reason_codes=("DROP_OLDEST",),
                        )
                    if not result.accepted:
                        self._finish_opportunity(
                            work,
                            "RESULT_QUEUE_DROPPED",
                            detections=detections,
                            reason_codes=("QUEUE_RETRY_FAILED",),
                        )
                else:
                    self._finish_opportunity(work, "DETECTOR_FAILED", reason_codes=("DETECTOR_EXCEPTION",))

                with self._detector_busy_lock:
                    self._detector_busy[label] = False

                handled = True

            if not handled:
                time.sleep(0.005)

    def _stereo_loop(self) -> None:
        """Stereo matching loop.

        Buffers left/right detections and invokes stereo callback when pairs are available.
        """
        while self._detection_running:
            try:
                result = self._detect_result_queue.get(timeout=0.2)
            except queue.Empty:
                # Check adaptive queue sizing during idle time
                self._check_adaptive_queue_sizing()
                continue

            label = result.work.label
            frame = result.work.frame
            detections = result.detections
            # Notify stereo callback for each result
            if self._stereo_callback:
                with self._detection_error_lock:
                    self._processing_attempts["results"] += 1
                try:
                    self._stereo_callback(label, frame, detections)
                except Exception as exc:
                    with self._detection_error_lock:
                        self._processing_failures["results"] += 1
                    logger.exception("Detection result processing failed for %s camera", label)
                    publish_error(
                        category=ErrorCategory.DETECTION,
                        severity=ErrorSeverity.ERROR,
                        message=f"Detection result processing failed for {label} camera",
                        source="DetectionThreadPool.results",
                        exception=exc,
                        camera=label,
                    )
                    self._finish_opportunity(
                        result.work,
                        "RESULT_PROCESSING_FAILED",
                        detections=detections,
                        reason_codes=(exc.__class__.__name__,),
                    )
                else:
                    self._finish_opportunity(result.work, "PROCESSING_COMPLETE", detections=detections)
            else:
                self._finish_opportunity(
                    result.work,
                    "RESULT_PROCESSING_FAILED",
                    detections=detections,
                    reason_codes=("STEREO_CALLBACK_MISSING",),
                )

            # Periodically check adaptive queue sizing
            self._check_adaptive_queue_sizing()

    def _publish_opportunity(self, work: _FrameWorkItem) -> None:
        callback = self._frame_opportunity_callback
        if callback is None:
            return
        frame = work.frame
        try:
            callback(
                FrameProcessingOpportunityEvent(
                    opportunity_id=work.opportunity_id,
                    frame_id=frame_decision_id(frame),
                    camera_id=frame.camera_id,
                    frame_index=frame.frame_index,
                    timestamp_ns=frame.t_capture_monotonic_ns,
                )
            )
        except Exception:
            logger.exception("Frame opportunity callback failed")

    def _finish_opportunity(
        self,
        work: _FrameWorkItem,
        status: str,
        *,
        detections: Optional[list[Detection]] = None,
        reason_codes: tuple[str, ...] = (),
    ) -> None:
        with self._detection_error_lock:
            if work.opportunity_id in self._terminal_opportunities:
                return
            if work.opportunity_id not in self._open_opportunities:
                return
            self._terminal_opportunities.add(work.opportunity_id)
            self._terminal_outcomes[status] += 1
            self._open_opportunities.pop(work.opportunity_id, None)
        callback = self._frame_outcome_callback
        if callback is None:
            return
        frame = work.frame
        try:
            callback(
                FrameProcessingOutcomeEvent(
                    opportunity_id=work.opportunity_id,
                    frame_id=frame_decision_id(frame),
                    camera_id=frame.camera_id,
                    frame_index=frame.frame_index,
                    timestamp_ns=frame.t_capture_monotonic_ns,
                    status=status,
                    detections=tuple(detections or ()),
                    reason_codes=tuple(reason_codes),
                )
            )
        except Exception:
            logger.exception("Frame terminal-outcome callback failed")


def _rate_payload(numerator: int, denominator: int) -> dict:
    """Build rate evidence without inventing a value when no work was attempted."""
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": (float(numerator) / float(denominator)) if denominator > 0 else None,
    }
