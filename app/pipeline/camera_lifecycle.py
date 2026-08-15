"""Camera lifecycle management: reconnection and recovery."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from capture import CameraDevice
from configs.settings import AppConfig

from app.camera import CameraReconnectionManager

from .camera_backend_factory import CameraBackendFactory
from .camera_frame_router import CameraFrameRouter

logger = logging.getLogger(__name__)


class CameraLifecycleManager:
    """Manages camera reconnection and recovery.

    Wraps CameraReconnectionManager and coordinates with the frame router
    and backend factory to transparently recover from disconnections.
    """

    def __init__(
        self,
        factory: CameraBackendFactory,
        frame_router: CameraFrameRouter,
        camera_lock: threading.Lock,
    ):
        """Initialize lifecycle manager.

        Args:
            factory: Backend factory for building replacement cameras
            frame_router: Frame router owning capture threads
            camera_lock: Lock protecting camera device references
        """
        self._factory = factory
        self._frame_router = frame_router
        self._camera_lock = camera_lock
        self._reconnection_mgr: Optional[CameraReconnectionManager] = None
        self._config: Optional[AppConfig] = None

        # References updated on reconnect — set by facade
        self._left_ref_setter: Optional[callable] = None
        self._right_ref_setter: Optional[callable] = None
        self._left_id: Optional[str] = None
        self._right_id: Optional[str] = None
        self._build_camera_fn: Optional[callable] = None
        self._get_camera_fn: Optional[callable] = None

    @property
    def reconnection_manager(self) -> Optional[CameraReconnectionManager]:
        """Return underlying reconnection manager."""
        return self._reconnection_mgr

    def initialize(
        self,
        config: AppConfig,
        left_id: str,
        right_id: str,
        left_ref_setter: callable,
        right_ref_setter: callable,
        build_camera_fn: callable = None,
        get_camera_fn: callable = None,
    ) -> None:
        """Initialize reconnection after cameras are started.

        Args:
            config: App config for re-configuring cameras
            left_id: Left camera serial
            right_id: Right camera serial
            left_ref_setter: Callable to update left camera reference
            right_ref_setter: Callable to update right camera reference
            build_camera_fn: Optional override for building cameras
            get_camera_fn: Callable(camera_id) returning current CameraDevice
        """
        self._config = config
        self._left_id = left_id
        self._right_id = right_id
        self._left_ref_setter = left_ref_setter
        self._right_ref_setter = right_ref_setter
        self._build_camera_fn = build_camera_fn or self._factory.build_camera
        self._get_camera_fn = get_camera_fn

        self._reconnection_mgr = CameraReconnectionManager(
            max_reconnect_attempts=5, base_delay=1.0, max_delay=30.0
        )
        self._reconnection_mgr.set_reconnect_callback(self._try_reconnect_camera)
        self._reconnection_mgr.register_camera("left")
        self._reconnection_mgr.register_camera("right")
        self._frame_router.set_reconnection_manager(self._reconnection_mgr)
        logger.info("Camera reconnection enabled")

    def shutdown(self) -> None:
        """Unregister cameras from reconnection manager."""
        if self._reconnection_mgr:
            try:
                if self._left_id:
                    self._reconnection_mgr.unregister_camera("left")
                if self._right_id:
                    self._reconnection_mgr.unregister_camera("right")
            except Exception as exc:
                logger.warning(f"Error unregistering cameras from reconnection manager: {exc}")
        self._frame_router.set_reconnection_manager(None)

    def set_state_change_callback(self, callback) -> None:
        """Proxy state change callback to reconnection manager."""
        if self._reconnection_mgr:
            self._reconnection_mgr.set_state_change_callback(callback)

    def _try_reconnect_camera(self, camera_id: str) -> bool:
        """Attempt to reconnect a disconnected camera.

        Args:
            camera_id: Camera identifier ("left" or "right")

        Returns:
            True if reconnection succeeded
        """
        logger.info(f"Attempting to reconnect {camera_id} camera")

        is_left = camera_id == "left"
        serial = self._left_id if is_left else self._right_id
        stop_event = self._frame_router.left_stop if is_left else self._frame_router.right_stop

        if not serial or not self._config:
            logger.error(f"Missing serial or config for {camera_id} camera")
            return False

        # Stop existing capture thread for this camera
        stop_event.set()
        thread_ref = self._frame_router.get_thread(camera_id)
        if thread_ref is not None and thread_ref.is_alive():
            try:
                thread_ref.join(timeout=2.0)
                if thread_ref.is_alive():
                    logger.warning(f"{camera_id} capture thread did not stop before reconnect")
            except Exception as exc:
                logger.warning(f"Error joining {camera_id} thread: {exc}")

        # Close existing camera if still open (loop has exited so close()
        # cannot race an in-flight read_frame on the same device).
        if self._get_camera_fn:
            old_camera = self._get_camera_fn(camera_id)
            if old_camera is not None:
                try:
                    old_camera.close()
                    logger.debug(f"{camera_id} camera closed for reconnection")
                except Exception as exc:
                    logger.warning(f"Error closing {camera_id} camera: {exc}")

        new_camera: Optional[CameraDevice] = None
        try:
            new_camera = self._build_camera_fn()
            label = "left" if is_left else "right"
            self._factory.open_camera(new_camera, serial, label)
            self._factory.configure_camera(new_camera, self._config, is_left)

            # Update reference under lock
            stop_event.clear()
            with self._camera_lock:
                if is_left:
                    self._left_ref_setter(new_camera)
                else:
                    self._right_ref_setter(new_camera)

            # Restart capture thread
            new_thread = self._frame_router.start_single_thread(
                camera_id, new_camera, stop_event
            )
            self._frame_router.set_thread(camera_id, new_thread)

            logger.info(f"Successfully reconnected {camera_id} camera")
            return True

        except Exception as exc:
            if new_camera is not None:
                try:
                    new_camera.close()
                except Exception as close_exc:
                    logger.warning(f"Failed to close rejected {camera_id} camera: {close_exc}")
            logger.error(f"Failed to reconnect {camera_id} camera: {exc}", exc_info=True)
            return False
