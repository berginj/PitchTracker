"""Detection threading pool for managing detection workers and stereo matching."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

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
        self._queue_put_drop_oldest(target, frame)

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

    def _reset_queues(self) -> None:
        """Reset all detection queues."""
        self._left_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._right_detect_queue = queue.Queue(maxsize=self._queue_size)
        self._detect_result_queue = queue.Queue(maxsize=self._queue_size * 4)

    @staticmethod
    def _queue_put_drop_oldest(target: queue.Queue, item) -> None:
        """Put item in queue, dropping oldest if full.

        Args:
            target: Queue to put item in
            item: Item to put
        """
        try:
            target.put_nowait(item)
            return
        except queue.Full:
            pass

        # Drop oldest item
        try:
            target.get_nowait()
        except queue.Empty:
            pass

        # Try again
        try:
            target.put_nowait(item)
        except queue.Full:
            pass

    def _detect_frame(self, label: str, frame: Frame) -> list[Detection]:
        """Detect frame using callback.

        Args:
            label: Camera label
            frame: Frame to detect

        Returns:
            List of detections
        """
        if self._detect_callback is None:
            return []

        try:
            return self._detect_callback(label, frame)
        except Exception:
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
            self._queue_put_drop_oldest(self._detect_result_queue, (label, frame, detections))

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
                self._queue_put_drop_oldest(self._detect_result_queue, (label, frame, detections))

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
