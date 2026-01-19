"""Camera reconnection logic for handling camera disconnections."""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

from app.events import ErrorCategory, ErrorSeverity, publish_error

logger = logging.getLogger(__name__)


class CameraState(Enum):
    """Camera connection state."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class CameraReconnectionManager:
    """Manager for automatic camera reconnection.

    Handles camera disconnections by attempting automatic reconnection
    with exponential backoff.
    """

    def __init__(
        self,
        max_reconnect_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        """Initialize camera reconnection manager.

        Args:
            max_reconnect_attempts: Maximum reconnection attempts
            base_delay: Base delay for exponential backoff (seconds)
            max_delay: Maximum delay between attempts (seconds)
        """
        self._max_attempts = max_reconnect_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay

        # State tracking
        self._camera_states: dict[str, CameraState] = {}
        self._reconnect_attempts: dict[str, int] = {}
        self._reconnect_threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

        # Callbacks
        self._reconnect_callback: Optional[Callable[[str], bool]] = None
        self._state_change_callback: Optional[Callable[[str, CameraState], None]] = None

    def set_reconnect_callback(self, callback: Callable[[str], bool]) -> None:
        """Set callback for camera reconnection.

        Args:
            callback: Function that takes camera_id and returns True if reconnection succeeded
        """
        self._reconnect_callback = callback

    def set_state_change_callback(self, callback: Callable[[str, CameraState], None]) -> None:
        """Set callback for camera state changes.

        Args:
            callback: Function that takes (camera_id, new_state)
        """
        self._state_change_callback = callback

    def register_camera(self, camera_id: str) -> None:
        """Register camera for monitoring.

        Args:
            camera_id: Camera identifier
        """
        with self._lock:
            if camera_id not in self._camera_states:
                self._camera_states[camera_id] = CameraState.CONNECTED
                self._reconnect_attempts[camera_id] = 0
                logger.info(f"Registered camera for reconnection monitoring: {camera_id}")

    def unregister_camera(self, camera_id: str) -> None:
        """Unregister camera from monitoring.

        Args:
            camera_id: Camera identifier
        """
        with self._lock:
            if camera_id in self._camera_states:
                # Stop any ongoing reconnection
                if camera_id in self._reconnect_threads:
                    thread = self._reconnect_threads[camera_id]
                    # Thread will stop on next iteration check
                    del self._reconnect_threads[camera_id]

                del self._camera_states[camera_id]
                del self._reconnect_attempts[camera_id]
                logger.info(f"Unregistered camera from reconnection monitoring: {camera_id}")

    def report_disconnection(self, camera_id: str) -> None:
        """Report camera disconnection.

        Args:
            camera_id: Camera identifier that disconnected
        """
        with self._lock:
            if camera_id not in self._camera_states:
                logger.warning(f"Disconnection reported for unregistered camera: {camera_id}")
                return

            if self._camera_states[camera_id] == CameraState.DISCONNECTED:
                # Already handling disconnection
                return

            self._set_state(camera_id, CameraState.DISCONNECTED)
            self._reconnect_attempts[camera_id] = 0

        # Publish error event
        publish_error(
            category=ErrorCategory.CAMERA,
            severity=ErrorSeverity.ERROR,
            message=f"Camera {camera_id} disconnected",
            source="CameraReconnectionManager",
            camera_id=camera_id,
        )

        # Start reconnection in background
        self._start_reconnection(camera_id)

    def report_connection_success(self, camera_id: str) -> None:
        """Report successful camera connection.

        Args:
            camera_id: Camera identifier
        """
        with self._lock:
            if camera_id in self._camera_states:
                self._set_state(camera_id, CameraState.CONNECTED)
                self._reconnect_attempts[camera_id] = 0
                logger.info(f"Camera {camera_id} connected successfully")

    def get_camera_state(self, camera_id: str) -> Optional[CameraState]:
        """Get current camera state.

        Args:
            camera_id: Camera identifier

        Returns:
            Camera state or None if not registered
        """
        with self._lock:
            return self._camera_states.get(camera_id)

    def _set_state(self, camera_id: str, state: CameraState) -> None:
        """Set camera state and notify callback.

        Args:
            camera_id: Camera identifier
            state: New state

        Note:
            Must be called with lock held
        """
        old_state = self._camera_states.get(camera_id)
        self._camera_states[camera_id] = state

        if old_state != state:
            logger.info(f"Camera {camera_id} state changed: {old_state} -> {state}")

            # Notify callback (outside lock to avoid deadlock)
            if self._state_change_callback:
                try:
                    # Release lock temporarily for callback
                    self._lock.release()
                    try:
                        self._state_change_callback(camera_id, state)
                    finally:
                        self._lock.acquire()
                except Exception as e:
                    logger.error(f"State change callback failed: {e}")

    def _start_reconnection(self, camera_id: str) -> None:
        """Start reconnection thread for camera.

        Args:
            camera_id: Camera identifier
        """
        with self._lock:
            # Check if already reconnecting
            if camera_id in self._reconnect_threads:
                thread = self._reconnect_threads[camera_id]
                if thread.is_alive():
                    logger.debug(f"Reconnection already in progress for {camera_id}")
                    return

            # Create reconnection thread
            thread = threading.Thread(
                target=self._reconnection_loop,
                args=(camera_id,),
                name=f"CameraReconnect-{camera_id}",
                daemon=False,
            )
            self._reconnect_threads[camera_id] = thread
            thread.start()
            logger.info(f"Started reconnection thread for camera {camera_id}")

    def _reconnection_loop(self, camera_id: str) -> None:
        """Reconnection loop with exponential backoff.

        Args:
            camera_id: Camera identifier
        """
        while True:
            with self._lock:
                # Check if still registered and disconnected
                if camera_id not in self._camera_states:
                    logger.debug(f"Camera {camera_id} unregistered, stopping reconnection")
                    break

                if self._camera_states[camera_id] == CameraState.CONNECTED:
                    logger.info(f"Camera {camera_id} already connected, stopping reconnection")
                    break

                attempt = self._reconnect_attempts[camera_id]

                # Check max attempts
                if attempt >= self._max_attempts:
                    self._set_state(camera_id, CameraState.FAILED)
                    publish_error(
                        category=ErrorCategory.CAMERA,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"Camera {camera_id} reconnection failed after {attempt} attempts",
                        source="CameraReconnectionManager",
                        camera_id=camera_id,
                        attempts=attempt,
                    )
                    break

                self._reconnect_attempts[camera_id] += 1
                self._set_state(camera_id, CameraState.RECONNECTING)

            # Calculate delay with exponential backoff
            delay = min(self._base_delay * (2 ** attempt), self._max_delay)
            logger.info(
                f"Attempting reconnection for camera {camera_id} "
                f"(attempt {attempt + 1}/{self._max_attempts}) in {delay:.1f}s"
            )
            time.sleep(delay)

            # Attempt reconnection
            if self._reconnect_callback:
                try:
                    success = self._reconnect_callback(camera_id)

                    if success:
                        with self._lock:
                            self._set_state(camera_id, CameraState.CONNECTED)
                            self._reconnect_attempts[camera_id] = 0

                        publish_error(
                            category=ErrorCategory.CAMERA,
                            severity=ErrorSeverity.INFO,
                            message=f"Camera {camera_id} reconnected successfully",
                            source="CameraReconnectionManager",
                            camera_id=camera_id,
                            attempts=attempt + 1,
                        )
                        break
                    else:
                        logger.warning(f"Reconnection attempt {attempt + 1} failed for {camera_id}")

                except Exception as e:
                    logger.error(f"Reconnection attempt {attempt + 1} error for {camera_id}: {e}")

        # Cleanup thread reference
        with self._lock:
            if camera_id in self._reconnect_threads:
                del self._reconnect_threads[camera_id]


__all__ = [
    "CameraState",
    "CameraReconnectionManager",
]
