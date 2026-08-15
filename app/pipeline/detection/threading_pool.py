"""Detection threading pool for managing detection workers and stereo matching."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter
from typing import Callable, Dict, List, Optional
from app.events import ErrorCategory, ErrorSeverity, publish_error
from app.events.event_types import FrameProcessingOpportunityEvent, FrameProcessingOutcomeEvent
from app.pipeline.detection.decision_ids import frame_decision_id
from app.pipeline.detection.threading_items import FrameWorkItem
from app.pipeline.detection.threading_queue import DetectionQueueMixin
from app.pipeline.detection.threading_stats import DetectionStatsMixin
from app.pipeline.detection.threading_workers import DetectionWorkerMixin
from contracts import Detection, Frame

logger = logging.getLogger(__name__)


class DetectionThreadPool(DetectionQueueMixin, DetectionWorkerMixin, DetectionStatsMixin):
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
        self._left_detect_queue: queue.Queue[FrameWorkItem] = queue.Queue()
        self._right_detect_queue: queue.Queue[FrameWorkItem] = queue.Queue()
        self._detect_result_queue: queue.Queue = queue.Queue()
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
        self._open_opportunities: Dict[str, FrameWorkItem] = {}
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
            work = FrameWorkItem(opportunity_id, label, frame)
            self._open_opportunities[opportunity_id] = work
        self._publish_opportunity(work)
        result = self._queue_put_drop_oldest(target, work, queue_name=label)
        if isinstance(result.displaced, FrameWorkItem):
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
