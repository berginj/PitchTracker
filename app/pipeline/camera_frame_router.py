"""Frame capture loop, callback routing, and frame validation."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from capture import CameraDevice
from contracts import Frame
from exceptions import CameraConnectionError

from app.camera import CameraReconnectionManager

logger = logging.getLogger(__name__)

# Maximum consecutive frame read failures before stopping capture
MAX_CONSECUTIVE_FAILURES = 10

# Time without frames before considering camera stalled (seconds)
FRAME_STALL_TIMEOUT = 5.0


class CameraFrameRouter:
    """Manages capture loops, frame validation, and callback dispatch.

    Each camera runs in its own daemon thread. Frames are validated before
    being dispatched to preview state and the frame callback.
    """

    def __init__(self) -> None:
        """Initialize the frame router."""
        self._capture_running = False
        self._threads_lock = threading.RLock()

        # Threads
        self._left_thread: Optional[threading.Thread] = None
        self._right_thread: Optional[threading.Thread] = None

        # Per-camera stop signals
        self._left_stop = threading.Event()
        self._right_stop = threading.Event()

        # Callbacks
        self._on_frame_captured: Optional[Callable[[str, Frame], None]] = None
        self._on_camera_error: Optional[Callable[[str, str], None]] = None
        self._on_frame_for_preview: Optional[Callable[[str, Frame], None]] = None

        # Reconnection manager reference
        self._reconnection_mgr: Optional[CameraReconnectionManager] = None

    @property
    def capture_running(self) -> bool:
        """Whether capture loops are active."""
        return self._capture_running

    @property
    def left_stop(self) -> threading.Event:
        """Left camera stop event (for reconnection)."""
        return self._left_stop

    @property
    def right_stop(self) -> threading.Event:
        """Right camera stop event (for reconnection)."""
        return self._right_stop

    def set_frame_callback(self, callback: Callable[[str, Frame], None]) -> None:
        """Set callback for frame captured events."""
        self._on_frame_captured = callback

    def set_error_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for camera error events."""
        self._on_camera_error = callback

    def set_preview_callback(self, callback: Callable[[str, Frame], None]) -> None:
        """Set callback to update preview state on valid frame."""
        self._on_frame_for_preview = callback

    def set_reconnection_manager(self, mgr: Optional[CameraReconnectionManager]) -> None:
        """Set reconnection manager for disconnect reporting."""
        self._reconnection_mgr = mgr

    def start_threads(
        self, left_camera: CameraDevice, right_camera: CameraDevice
    ) -> None:
        """Start capture threads for both cameras.

        Args:
            left_camera: Opened left camera device
            right_camera: Opened right camera device
        """
        with self._threads_lock:
            if any(thread is not None and thread.is_alive()
                   for thread in (self._left_thread, self._right_thread)):
                raise CameraConnectionError("Previous capture threads are still stopping; retry stop before restart")
            self._capture_running = True
            self._left_stop = threading.Event()
            self._right_stop = threading.Event()
            self._left_thread = self.start_single_thread("left", left_camera, self._left_stop)
            self._right_thread = self.start_single_thread("right", right_camera, self._right_stop)

    def start_single_thread(
        self, label: str, camera: CameraDevice, stop_event: threading.Event
    ) -> threading.Thread:
        """Start a capture thread for a single camera (used by reconnection).

        Args:
            label: Camera label ("left" or "right")
            camera: Camera device to capture from
            stop_event: Stop signal for the loop

        Returns:
            The started thread
        """
        with self._threads_lock:
            previous = self.get_thread(label)
            if not self._capture_running or (previous is not None and previous.is_alive()):
                raise CameraConnectionError(f"Cannot restart {label} capture until the previous reader stops")
            thread = threading.Thread(
                target=self._capture_loop,
                args=(label, camera, stop_event),
                name=f"Capture-{label}",
                daemon=True,
            )
            self.set_thread(label, thread)
            thread.start()
            return thread

    def request_stop(self) -> None:
        """Fence new reader starts before waiting for native operations."""
        with self._threads_lock:
            self._capture_running = False
            self._left_stop.set()
            self._right_stop.set()

    def stop(self, timeout: float = 1.0) -> bool:
        """Join readers while retaining ownership of any timed-out thread."""
        self.request_stop()
        deadline = time.monotonic() + timeout
        stopped = True
        for label in ("left", "right"):
            thread = self.get_thread(label)
            if thread is None:
                continue
            if thread is threading.current_thread():
                stopped = False
                continue
            try:
                thread.join(timeout=max(0.0, deadline - time.monotonic()))
            except RuntimeError:
                # A thread whose start failed never acquired a native reader.
                if thread.ident is not None:
                    raise
            if thread.is_alive():
                stopped = False
                logger.warning("%s capture thread is still stopping; resources remain owned", label)
            else:
                with self._threads_lock:
                    if self.get_thread(label) is thread:
                        self.set_thread(label, None)
        return stopped

    def get_thread(self, label: str) -> Optional[threading.Thread]:
        """Get the owned reader, including one still stopping after a timeout."""
        with self._threads_lock:
            return self._left_thread if label == "left" else self._right_thread

    def set_thread(self, label: str, thread: Optional[threading.Thread]) -> None:
        with self._threads_lock:
            if label == "left":
                self._left_thread = thread
            else:
                self._right_thread = thread

    def _capture_loop(
        self, label: str, camera: CameraDevice, stop_event: threading.Event
    ) -> None:
        """Main capture loop for a camera.

        Reads frames, validates, updates preview, fires callback.
        Implements stall detection and consecutive failure tracking.
        """
        consecutive_failures = 0
        last_frame_time = time.monotonic()
        total_frames = 0

        logger.info(f"Camera {label}: Capture loop started")

        while self._capture_running and not stop_event.is_set():
            try:
                frame = camera.read_frame(timeout_ms=200)
                if stop_event.is_set() or not self._capture_running:
                    break

                consecutive_failures = 0
                last_frame_time = time.monotonic()
                total_frames += 1

                if not _validate_frame(label, frame):
                    logger.warning(f"Camera {label}: Invalid frame received (frame {total_frames})")
                    continue

                # Update preview state
                if self._on_frame_for_preview:
                    self._on_frame_for_preview(label, frame)

                # Notify parent via callback
                if self._on_frame_captured:
                    try:
                        self._on_frame_captured(label, frame)
                    except Exception as e:
                        logger.error(
                            f"Camera {label}: Error in frame callback: {e}",
                            exc_info=True,
                        )

            except TimeoutError:
                logger.debug(f"Camera {label}: Frame read timeout")
                continue

            except Exception as exc:
                consecutive_failures += 1
                logger.error(
                    f"Camera {label}: Frame read failed "
                    f"(attempt {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {exc}",
                    exc_info=True,
                )

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    error_msg = (
                        f"Camera {label} failed after {MAX_CONSECUTIVE_FAILURES} "
                        f"consecutive attempts. Last error: {exc}"
                    )
                    logger.critical(error_msg)
                    if self._on_camera_error:
                        self._on_camera_error(label, error_msg)
                    if self._reconnection_mgr:
                        self._reconnection_mgr.report_disconnection(label)
                    break

            # Stall detection
            time_since_frame = time.monotonic() - last_frame_time
            if time_since_frame > FRAME_STALL_TIMEOUT:
                error_msg = (
                    f"Camera {label} stalled - no frames for {time_since_frame:.1f} seconds"
                )
                logger.critical(error_msg)
                if self._on_camera_error:
                    self._on_camera_error(label, error_msg)
                if self._reconnection_mgr:
                    self._reconnection_mgr.report_disconnection(label)
                break

        logger.info(
            f"Camera {label}: Capture loop stopped "
            f"(total_frames={total_frames}, failures={consecutive_failures})"
        )


def _validate_frame(label: str, frame: Frame) -> bool:
    """Validate that a frame is usable.

    Args:
        label: Camera label for logging
        frame: Frame to validate

    Returns:
        True if frame is valid
    """
    import numpy as np

    if frame is None:
        logger.error(f"Camera {label}: Frame is None")
        return False

    if frame.image is None:
        logger.error(f"Camera {label}: Frame image is None")
        return False

    if frame.width <= 0 or frame.height <= 0:
        logger.error(f"Camera {label}: Invalid dimensions {frame.width}x{frame.height}")
        return False

    if isinstance(frame.image, np.ndarray):
        if np.all(frame.image == 0):
            logger.warning(f"Camera {label}: All-zero frame detected")
            return False

    return True
