"""Frame capture loop, callback routing, and frame validation."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from capture import CameraDevice
from contracts import Frame

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
        self._capture_running = True
        self._left_stop.clear()
        self._right_stop.clear()
        self._left_thread = threading.Thread(
            target=self._capture_loop,
            args=("left", left_camera, self._left_stop),
            name="Capture-left",
            daemon=True,
        )
        self._right_thread = threading.Thread(
            target=self._capture_loop,
            args=("right", right_camera, self._right_stop),
            name="Capture-right",
            daemon=True,
        )
        self._left_thread.start()
        self._right_thread.start()

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
        thread = threading.Thread(
            target=self._capture_loop,
            args=(label, camera, stop_event),
            name=f"Capture-{label}",
            daemon=True,
        )
        thread.start()
        return thread

    def stop(self) -> None:
        """Signal all loops to stop and join threads."""
        self._capture_running = False
        self._left_stop.set()
        self._right_stop.set()

        for label, thread in [("left", self._left_thread), ("right", self._right_thread)]:
            if thread is not None:
                try:
                    thread.join(timeout=1.0)
                    if thread.is_alive():
                        logger.warning(f"{label.capitalize()} capture thread did not stop within timeout")
                except Exception as exc:
                    logger.warning(f"Error joining {label} capture thread: {exc}")

        self._left_thread = None
        self._right_thread = None

    def get_thread(self, label: str) -> Optional[threading.Thread]:
        """Get the thread for a camera label."""
        if label == "left":
            return self._left_thread
        return self._right_thread

    def set_thread(self, label: str, thread: Optional[threading.Thread]) -> None:
        """Set the thread reference for a camera label."""
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
