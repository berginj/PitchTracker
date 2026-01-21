"""CaptureService interface for camera management and frame capture.

Responsibility: Manage camera lifecycle, capture frames, handle reconnection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from capture.camera_device import CameraStats
from configs.settings import AppConfig
from contracts import Frame


# Type aliases for callbacks
FrameCallback = Callable[[str, Frame], None]
"""Callback invoked when a frame is captured.

Args:
    camera_id: Camera identifier ("left" or "right")
    frame: Captured frame
"""

CameraStateCallback = Callable[[str, object], None]
"""Callback invoked when camera connection state changes.

Args:
    camera_id: Camera identifier ("left" or "right")
    state: New camera state (CameraState enum)
"""


class CaptureService(ABC):
    """Abstract interface for camera capture service.

    Manages camera lifecycle:
    - Opening/closing cameras
    - Frame capture and buffering
    - Stats collection
    - Reconnection handling

    Thread-Safety:
        - start_capture() and stop_capture() are thread-safe
        - Frame callbacks may be invoked from camera threads
        - get_preview_frames() and get_stats() are thread-safe
    """

    @abstractmethod
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

    @abstractmethod
    def stop_capture(self) -> None:
        """Stop capturing and release camera resources.

        Thread-Safe: Can be called from any thread.
        Idempotent: Safe to call multiple times.
        """

    @abstractmethod
    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Get latest frames for UI preview.

        Returns:
            Tuple of (left_frame, right_frame)

        Raises:
            RuntimeError: If capture is not active

        Thread-Safe: Returns buffered frames, does not block capture.
        """

    @abstractmethod
    def get_stats(self) -> Dict[str, CameraStats]:
        """Get capture statistics for both cameras.

        Returns:
            Dict mapping camera_id to CameraStats

        Thread-Safe: Returns snapshot of current stats.
        """

    @abstractmethod
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

    @abstractmethod
    def enable_reconnection(self, enabled: bool) -> None:
        """Enable/disable automatic camera reconnection.

        Args:
            enabled: True to enable reconnection, False to disable

        Note: Only applies to physical cameras, not simulated cameras.
        """

    @abstractmethod
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

    @abstractmethod
    def is_capturing(self) -> bool:
        """Check if capture is currently active.

        Returns:
            True if capturing, False otherwise
        """
