"""Camera management facade for capture lifecycle and frame acquisition.

Delegates to focused collaborators:
- CameraBackendFactory: backend construction and configuration
- CameraFrameRouter: capture loops and callback routing
- CameraLifecycleManager: reconnection and recovery
- CameraPreviewStats: preview frames and statistics
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional, Tuple

from capture import CameraDevice
from configs.settings import AppConfig
from contracts import Frame
from exceptions import (
    CameraConfigurationError,
    CameraConnectionError,
)

from app.events import publish_error, ErrorCategory, ErrorSeverity
from app.camera import CameraState

from .camera_backend_factory import CameraBackendFactory
from .camera_frame_router import CameraFrameRouter
from .camera_lifecycle import CameraLifecycleManager
from .camera_preview_stats import CameraPreviewStats
from .initialization import PipelineInitializer

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages camera lifecycle, capture threads, and frame acquisition.

    Thin facade delegating to backend factory, frame router, lifecycle
    manager, and preview/stats collaborators. Preserves the original
    public API surface.
    """

    def __init__(self, backend: str, initializer: PipelineInitializer):
        """Initialize camera manager.

        Args:
            backend: Camera backend ("uvc", "opencv", or "sim")
            initializer: PipelineInitializer for camera configuration
        """
        self._backend = backend
        self._initializer = initializer

        # Camera instances
        self._left: Optional[CameraDevice] = None
        self._right: Optional[CameraDevice] = None
        self._left_id: Optional[str] = None
        self._right_id: Optional[str] = None

        # Lock for swapping device references during reconnection
        self._camera_lock = threading.Lock()

        # Collaborators
        self._factory = CameraBackendFactory(backend)
        self._frame_router = CameraFrameRouter()
        self._preview = CameraPreviewStats()
        self._lifecycle = CameraLifecycleManager(
            self._factory, self._frame_router, self._camera_lock
        )

        # Wire preview callback into frame router
        self._frame_router.set_preview_callback(self._preview.update_frame)

        # Reconnection policy
        self._enable_reconnection = backend != "sim"

    # ------------------------------------------------------------------
    # Public API — callbacks
    # ------------------------------------------------------------------

    def set_frame_callback(self, callback: Callable[[str, Frame], None]) -> None:
        """Set callback for frame captured events."""
        self._frame_router.set_frame_callback(callback)

    def set_error_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for camera error events."""
        self._frame_router.set_error_callback(callback)

    def set_camera_state_callback(
        self, callback: Callable[[str, CameraState], None]
    ) -> None:
        """Set callback for camera state changes (for UI updates)."""
        self._lifecycle.set_state_change_callback(callback)

    def enable_reconnection(self, enabled: bool = True) -> None:
        """Enable or disable automatic camera reconnection."""
        self._enable_reconnection = enabled and self._backend != "sim"
        logger.info(
            f"Camera reconnection {'enabled' if self._enable_reconnection else 'disabled'}"
        )

    # ------------------------------------------------------------------
    # Public API — capture lifecycle
    # ------------------------------------------------------------------

    def start_capture(
        self,
        config: AppConfig,
        left_serial: str,
        right_serial: str,
    ) -> None:
        """Start capture on both cameras.

        Opens cameras, configures them, and starts capture threads.

        Raises:
            CameraConnectionError: If cameras fail to open
            CameraConfigurationError: If camera configuration fails
        """
        logger.info(f"Starting capture with left={left_serial}, right={right_serial}")

        try:
            self._left_id = left_serial
            self._right_id = right_serial

            # Build camera objects
            try:
                self._left = self._build_camera()
                self._right = self._build_camera()
                logger.debug("Camera objects built successfully")
            except Exception as exc:
                logger.error(f"Failed to build camera objects: {exc}")
                publish_error(
                    category=ErrorCategory.CAMERA,
                    severity=ErrorSeverity.CRITICAL,
                    message=f"Failed to initialize camera objects: {exc}",
                    source="CameraManager.start_capture",
                    exception=exc,
                )
                raise CameraConnectionError(
                    f"Failed to initialize camera objects: {exc}"
                ) from exc

            # Open left camera
            self._factory.open_camera(self._left, left_serial, "left")

            # Open right camera (rollback left on failure)
            try:
                self._factory.open_camera(self._right, right_serial, "right")
            except CameraConnectionError:
                try:
                    self._left.close()
                except Exception:
                    pass
                raise

            # Configure both cameras
            try:
                self._factory.configure_camera(self._left, config, is_left=True)
                self._factory.configure_camera(self._right, config, is_left=False)
            except CameraConfigurationError as exc:
                error_msg = (
                    f"Failed to configure cameras: {exc}\n\n"
                    f"Both cameras opened successfully but configuration failed.\n\n"
                    f"Possible solutions:\n"
                    f"  • Check camera settings in default.yaml\n"
                    f"  • Verify cameras support requested resolution/FPS\n"
                    f"  • Try reducing FPS (e.g., from 60 to 30 FPS)\n"
                    f"  • Check that USB bandwidth is sufficient"
                )
                publish_error(
                    category=ErrorCategory.CAMERA,
                    severity=ErrorSeverity.ERROR,
                    message=f"Failed to configure cameras: {exc}",
                    source="CameraManager.start_capture",
                    exception=exc,
                    left_serial=left_serial,
                    right_serial=right_serial,
                )
                self._cleanup_cameras()
                raise CameraConfigurationError(error_msg) from exc.__cause__

            # Start capture threads
            try:
                self._frame_router.start_threads(self._left, self._right)
            except Exception as exc:
                logger.error(f"Failed to start capture threads: {exc}")
                publish_error(
                    category=ErrorCategory.CAMERA,
                    severity=ErrorSeverity.CRITICAL,
                    message="Failed to start capture threads",
                    source="CameraManager.start_capture",
                    exception=exc,
                )
                self._cleanup_cameras()
                raise CameraConnectionError(
                    f"Failed to start capture threads: {exc}"
                ) from exc

            # Initialize reconnection manager
            if self._enable_reconnection:
                self._lifecycle.initialize(
                    config=config,
                    left_id=left_serial,
                    right_id=right_serial,
                    left_ref_setter=self._set_left,
                    right_ref_setter=self._set_right,
                    build_camera_fn=self._build_camera,
                    get_camera_fn=self._get_camera,
                )

            logger.info("Capture started successfully")

        except (CameraConnectionError, CameraConfigurationError):
            raise
        except Exception as exc:
            logger.exception("Unexpected error during capture start")
            self._cleanup_cameras()
            raise CameraConnectionError(
                f"Unexpected error starting capture: {exc}"
            ) from exc

    def stop_capture(self) -> None:
        """Stop capture on both cameras. Best-effort, does not raise."""
        logger.info("Stopping capture")

        try:
            # Unregister from reconnection manager
            self._lifecycle.shutdown()

            # Stop capture threads
            self._frame_router.stop()

            # Close cameras
            if self._left is not None:
                try:
                    self._left.close()
                    logger.debug("Left camera closed")
                except Exception as exc:
                    logger.error(f"Error closing left camera: {exc}")
                finally:
                    self._left = None

            if self._right is not None:
                try:
                    self._right.close()
                    logger.debug("Right camera closed")
                except Exception as exc:
                    logger.error(f"Error closing right camera: {exc}")
                finally:
                    self._right = None

            logger.info("Capture stopped successfully")

        except Exception:
            logger.exception("Unexpected error during capture stop")

    # ------------------------------------------------------------------
    # Public API — queries
    # ------------------------------------------------------------------

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Get latest preview frames from both cameras.

        Raises:
            CameraConnectionError: If capture is not started
            PitchTrackerError: If frames are not yet available
        """
        cameras_active = self._left is not None and self._right is not None
        return self._preview.get_preview_frames(cameras_active)

    def get_stats(self):
        """Get camera statistics dictionary, or empty dict if not capturing."""
        return CameraPreviewStats.get_stats(self._left, self._right)

    def is_capturing(self) -> bool:
        """Check if capture is currently running."""
        return self._frame_router.capture_running

    def get_camera_ids(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current camera serial numbers."""
        return self._left_id, self._right_id

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @property
    def _left_thread(self):
        """Thread reference (compat shim for tests)."""
        return self._frame_router.get_thread("left")

    @_left_thread.setter
    def _left_thread(self, val):
        self._frame_router.set_thread("left", val)

    @property
    def _right_thread(self):
        """Thread reference (compat shim for tests)."""
        return self._frame_router.get_thread("right")

    @_right_thread.setter
    def _right_thread(self, val):
        self._frame_router.set_thread("right", val)

    def _set_left(self, camera: CameraDevice) -> None:
        """Update left camera reference (called by lifecycle manager)."""
        self._left = camera

    def _set_right(self, camera: CameraDevice) -> None:
        """Update right camera reference (called by lifecycle manager)."""
        self._right = camera

    def _get_camera(self, camera_id: str):
        """Get current camera device by id (called by lifecycle manager)."""
        if camera_id == "left":
            return self._left
        return self._right

    def _build_camera(self) -> CameraDevice:
        """Build camera instance (delegates to factory, kept for test compat)."""
        return self._factory.build_camera()

    def _try_reconnect_camera(self, camera_id: str) -> bool:
        """Reconnect camera (delegates to lifecycle, kept for test compat)."""
        return self._lifecycle._try_reconnect_camera(camera_id)

    def _validate_frame(self, label: str, frame) -> bool:
        """Validate frame (delegates to module function, kept for test compat)."""
        from .camera_frame_router import _validate_frame
        return _validate_frame(label, frame)

    def _cleanup_cameras(self) -> None:
        """Clean up camera resources on error."""
        try:
            if self._left is not None:
                self._left.close()
                self._left = None
        except Exception as exc:
            logger.warning(f"Error closing left camera during cleanup: {exc}")

        try:
            if self._right is not None:
                self._right.close()
                self._right = None
        except Exception as exc:
            logger.warning(f"Error closing right camera during cleanup: {exc}")
