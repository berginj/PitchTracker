"""Detection threading pool for managing detection workers and stereo matching."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

from app.events import ErrorCategory, ErrorSeverity, publish_error
from contracts import Detection, Frame

logger = logging.getLogger(__name__)


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
        self._left_detect_queue: queue.Queue[Frame] = queue.Queue()
        self._right_detect_queue: queue.Queue[Frame] = queue.Queue()
        self._detect_result_queue: queue.Queue[Tuple[str, Frame, list[Detection]]] = queue.Queue()
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

        # Error tracking
        self._detection_errors: Dict[str, int] = {"left": 0, "right": 0}
        self._detection_error_lock = threading.Lock()
        self._last_error_log_time: Dict[str, float] = {"left": 0.0, "right": 0.0}
        self._max_consecutive_errors = 10

        # Frame drop tracking
        self._frames_dropped: Dict[str, int] = {"left": 0, "right": 0, "results": 0}
        self._last_drop_log_time: Dict[str, float] = {"left": 0.0, "right": 0.0, "results": 0.0}
        self._drop_warning_threshold = 10  # Warn after this many drops

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
        self._detector_busy = {"left": False, "right": False}
        self._detector_threads = []
        self._worker_threads = []

        # Reset error tracking
        with self._detection_error_lock:
            self._detection_errors = {"left": 0, "right": 0}
            self._last_error_log_time = {"left": 0.0, "right": 0.0}

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
        self._queue_put_drop_oldest(target, frame, queue_name=label)

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

    def _reset_queues(self) -> None:
        """Reset all detection queues."""
        self._left_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._right_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._detect_result_queue = queue.Queue(maxsize=self._queue_size * 4)

    def _queue_put_drop_oldest(self, target: queue.Queue, item, queue_name: str = "unknown") -> None:
        """Put item in queue, dropping oldest if full.

        Optimized to minimize lock contention by releasing lock before I/O operations.

        Args:
            target: Queue to put item in
            item: Item to put
            queue_name: Name of queue for tracking/logging
        """
        try:
            target.put_nowait(item)
            return
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
        try:
            target.get_nowait()
        except queue.Empty:
            pass

        # Try again
        try:
            target.put_nowait(item)
        except queue.Full:
            logger.error(f"Failed to put item in queue '{queue_name}' even after dropping oldest")
            pass

    def _detect_frame(self, label: str, frame: Frame) -> list[Detection]:
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
        if self._detect_callback is None:
            return []

        try:
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
                    exc_info=True
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

            # Return empty list to allow pipeline to continue
            # but errors are now visible and tracked
            return []

    def _detection_loop_per_camera(self, label: str, source: queue.Queue) -> None:
        """Detection loop for per-camera mode (one thread per camera).

        Args:
            label: Camera label ("left" or "right")
            source: Queue to read frames from
        """
        while self._detection_running:
            try:
                frame = source.get(timeout=0.2)
            except queue.Empty:
                continue

            detections = self._detect_frame(label, frame)
            self._queue_put_drop_oldest(self._detect_result_queue, (label, frame, detections), queue_name="results")

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
                        frame = source.get_nowait()
                    except queue.Empty:
                        continue

                    self._detector_busy[label] = True

                # Process frame
                detections = self._detect_frame(label, frame)
                self._queue_put_drop_oldest(self._detect_result_queue, (label, frame, detections), queue_name="results")

                with self._detector_busy_lock:
                    self._detector_busy[label] = False

                handled = True

            if not handled:
                time.sleep(0.005)

    def _stereo_loop(self) -> None:
        """Stereo matching loop.

        Buffers left/right detections and invokes stereo callback when pairs are available.
        """
        left_buffer: deque[Tuple[Frame, list[Detection]]] = deque(maxlen=6)
        right_buffer: deque[Tuple[Frame, list[Detection]]] = deque(maxlen=6)

        while self._detection_running:
            try:
                label, frame, detections = self._detect_result_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if label == "left":
                left_buffer.append((frame, detections))
            else:
                right_buffer.append((frame, detections))

            # Notify stereo callback for each result
            if self._stereo_callback:
                self._stereo_callback(label, frame, detections)
