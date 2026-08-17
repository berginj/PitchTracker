"""CaptureService implementation with EventBus integration.

Manages camera lifecycle:
- Opening/closing cameras
- Frame capture and publishing to EventBus
- Stats collection
- Reconnection handling
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

from app.camera import CameraState
from app.events.event_bus import EventBus
from app.events.event_types import FrameCapturedEvent
from app.events.event_metadata import make_event_metadata
from app.pipeline.camera_management import CameraManager
from app.pipeline.initialization import PipelineInitializer
from app.services.capture.interface import (
    CaptureService,
    CameraStateCallback,
    FrameCallback,
)
from configs.settings import AppConfig
from contracts import Frame
from log_config.logger import get_logger

logger = get_logger(__name__)


class CaptureServiceImpl(CaptureService):
    """Event-driven capture service implementation.

    Features:
    - EventBus integration for event-driven frame publishing
    - Wraps CameraManager for camera lifecycle management
    - Thread-safe camera control
    - Automatic reconnection support
    - Stats collection

    Architecture:
        - Wraps CameraManager
        - Publishes FrameCapturedEvent to EventBus when frames are captured
        - Maintains callbacks for UI updates

    Thread Safety:
        - All public methods are thread-safe
        - Frame callbacks invoked from camera threads
        - EventBus publishing is thread-safe
    """

    def __init__(self, event_bus: EventBus, backend: str = "uvc"):
        """Initialize capture service.

        Args:
            event_bus: EventBus instance for publishing events
            backend: Camera backend ("uvc", "opencv", or "sim")
        """
        self._event_bus = event_bus
        self._backend = backend
        self._lock = threading.Lock()

        # Camera manager
        self._initializer = PipelineInitializer()
        self._camera_mgr = CameraManager(backend, self._initializer)

        # Set frame callback to publish events
        self._camera_mgr.set_frame_callback(self._on_frame_captured_internal)

        # State
        self._capturing = False
        self._config: Optional[AppConfig] = None
        self._config_path: Optional[Path] = None

        # Callbacks (for backward compatibility with UI)
        self._frame_callbacks: List[FrameCallback] = []
        self._state_callbacks: List[CameraStateCallback] = []
        self._session_id: Optional[str] = None

        logger.info(f"CaptureService initialized with backend={backend}")

    def start_capture(
        self,
        config: AppConfig,
        left_serial: str,
        right_serial: str,
        config_path: Optional[Path] = None,
    ) -> None:
        """Start capturing from both cameras.

        Args:
            config: Application configuration with camera settings
            left_serial: Serial number of left camera
            right_serial: Serial number of right camera
            config_path: Optional path to config file for hot-reloading

        Raises:
            CameraNotFoundError: If cameras cannot be found
            CameraConnectionError: If cameras cannot be opened
            CameraConfigurationError: If camera settings are invalid
        """
        with self._lock:
            if self._capturing:
                raise RuntimeError("Capture already started")

            self._config = config
            self._config_path = config_path

            # Start camera manager
            self._camera_mgr.start_capture(config, left_serial, right_serial)

            # Set camera state callback if any registered
            if self._state_callbacks:
                self._camera_mgr.set_camera_state_callback(self._on_camera_state_changed_internal)

            self._capturing = True
            logger.info(f"Capture started: left={left_serial}, right={right_serial}")

    def stop_capture(self) -> None:
        """Stop capturing and release camera resources.

        Thread-Safe: Can be called from any thread.
        Idempotent: Safe to call multiple times.
        """
        with self._lock:
            if not self._capturing:
                return

            self._camera_mgr.stop_capture()
            self._capturing = False
            self._config = None
            self._config_path = None

            logger.info("Capture stopped")

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Get latest frames for UI preview.

        Returns:
            Tuple of (left_frame, right_frame)

        Raises:
            RuntimeError: If capture is not active

        Thread-Safe: Returns buffered frames, does not block capture.
        """
        with self._lock:
            if not self._capturing:
                raise RuntimeError("Capture not active")

        return self._camera_mgr.get_preview_frames()

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get capture statistics for both cameras.

        Returns:
            Dict mapping camera_id to numeric statistics

        Thread-Safe: Returns snapshot of current stats.
        """
        with self._lock:
            if not self._capturing:
                return {}

        return cast(Dict[str, Dict[str, float]], self._camera_mgr.get_stats())

    def on_frame_captured(self, callback: FrameCallback) -> None:
        """Register callback for frame capture events.

        Callback will be invoked from camera thread when frame is captured.

        Args:
            callback: Function to call with (camera_id, frame)

        Thread-Safety:
            - Callback registration is thread-safe
            - Callback will be invoked from camera capture thread
            - Callback should be fast (< 5ms) to avoid blocking capture
        """
        with self._lock:
            self._frame_callbacks.append(callback)
            logger.debug(f"Registered frame callback ({len(self._frame_callbacks)} total)")

    def enable_reconnection(self, enabled: bool) -> None:
        """Enable/disable automatic camera reconnection.

        Args:
            enabled: True to enable reconnection, False to disable

        Note: Only applies to physical cameras, not simulated cameras.
        """
        with self._lock:
            self._camera_mgr.enable_reconnection(enabled)
            logger.info(f"Camera reconnection {'enabled' if enabled else 'disabled'}")

    def on_camera_state_changed(self, callback: CameraStateCallback) -> None:
        """Register callback for camera state changes.

        Callback will be invoked when camera connection state changes
        (connected, disconnected, reconnecting, failed).

        Args:
            callback: Function to call with (camera_id, state)

        Thread-Safety:
            - Callback registration is thread-safe
            - Callback invoked from reconnection thread
        """
        with self._lock:
            self._state_callbacks.append(callback)

            # If already capturing, set callback on manager
            if self._capturing:
                self._camera_mgr.set_camera_state_callback(self._on_camera_state_changed_internal)

            logger.debug(f"Registered camera state callback ({len(self._state_callbacks)} total)")

    def is_capturing(self) -> bool:
        """Check if capture is currently active."""
        with self._lock:
            return self._capturing

    def set_session_id(self, session_id: Optional[str]) -> None:
        """Set or clear the active session_id for event metadata."""
        with self._lock:
            self._session_id = session_id

    # Internal Event Handlers

    def _on_frame_captured_internal(self, camera_id: str, frame: Frame) -> None:
        """Internal frame capture handler.

        Publishes FrameCapturedEvent to EventBus and invokes registered callbacks.

        Args:
            camera_id: Camera identifier ("left" or "right")
            frame: Captured frame

        Note: Called from camera capture thread
        """
        try:
            # Publish to EventBus (PRIMARY path for event-driven architecture)
            sid = self._session_id
            event = FrameCapturedEvent(
                camera_id=camera_id,
                frame=frame,
                timestamp_ns=frame.t_capture_monotonic_ns,
                metadata=make_event_metadata(
                    "FrameCapturedEvent",
                    correlation_id=f"{camera_id}_{frame.frame_index}",
                    timestamp_ns=frame.t_capture_monotonic_ns,
                    camera_id=camera_id,
                    session_id=sid,
                ),
            )
            self._event_bus.publish(event)

            # Invoke registered callbacks (for backward compatibility).
            # Copy the list under the lock so concurrent on_frame_captured()
            # registration can't mutate it mid-iteration on this thread.
            with self._lock:
                callbacks = list(self._frame_callbacks)
            for callback in callbacks:
                try:
                    callback(camera_id, frame)
                except Exception as e:
                    logger.error(f"Frame callback error: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error handling frame capture: {e}", exc_info=True)

    def _on_camera_state_changed_internal(self, camera_id: str, state: CameraState) -> None:
        """Internal camera state change handler.

        Invokes all registered state callbacks.

        Args:
            camera_id: Camera identifier ("left" or "right")
            state: New camera state

        Note: Called from reconnection thread
        """
        try:
            for callback in self._state_callbacks:
                try:
                    callback(camera_id, state)
                except Exception as e:
                    logger.error(f"Camera state callback error: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error handling camera state change: {e}", exc_info=True)
