"""Camera lifecycle management: reconnection and recovery."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from capture import CameraDevice
from configs.settings import AppConfig
from exceptions import CameraConnectionError

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
        self._operation_lock = threading.Lock()
        self._cancel = threading.Event()
        self._cancel.set()
        self._generation = 0
        self._rejected_cameras: list[CameraDevice] = []

        # References updated on reconnect — set by facade
        self._left_ref_setter: Optional[Callable[[CameraDevice], None]] = None
        self._right_ref_setter: Optional[Callable[[CameraDevice], None]] = None
        self._left_id: Optional[str] = None
        self._right_id: Optional[str] = None
        self._build_camera_fn: Optional[Callable[[], CameraDevice]] = None
        self._get_camera_fn: Optional[Callable[[str], Optional[CameraDevice]]] = None

    @property
    def reconnection_manager(self) -> Optional[CameraReconnectionManager]:
        """Return underlying reconnection manager."""
        return self._reconnection_mgr

    def initialize(
        self,
        config: AppConfig,
        left_id: str,
        right_id: str,
        left_ref_setter: Callable[[CameraDevice], None],
        right_ref_setter: Callable[[CameraDevice], None],
        build_camera_fn: Optional[Callable[[], CameraDevice]] = None,
        get_camera_fn: Optional[Callable[[str], Optional[CameraDevice]]] = None,
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
        if not self._operation_lock.acquire(blocking=False):
            raise CameraConnectionError("Previous reconnection is still stopping")
        try:
            with self._camera_lock:
                self._generation += 1
                self._cancel.clear()
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
        finally:
            self._operation_lock.release()

    def shutdown(self, timeout: float = 1.0) -> bool:
        """Cancel and await reconnect ownership without closing live native I/O."""
        with self._camera_lock:
            self._generation += 1
            self._cancel.set()
        self._frame_router.set_reconnection_manager(None)
        manager = self._reconnection_mgr
        if manager is not None:
            manager.unregister_camera("left")
            manager.unregister_camera("right")
            threads_stopped = manager.wait_stopped(timeout)
        else:
            threads_stopped = True
        # Also cover directly invoked reconnect callbacks used by callers/tests.
        operation_stopped = self._operation_lock.acquire(timeout=timeout)
        cleanup_complete = True
        if operation_stopped:
            try:
                for camera in list(self._rejected_cameras):
                    try:
                        camera.close()
                    except Exception:
                        cleanup_complete = False
                        logger.exception("Rejected replacement remains owned; retry camera stop")
                    else:
                        self._rejected_cameras.remove(camera)
            finally:
                self._operation_lock.release()
        return threads_stopped and operation_stopped and cleanup_complete

    def set_state_change_callback(self, callback) -> None:
        """Proxy state change callback to reconnection manager."""
        if self._reconnection_mgr:
            self._reconnection_mgr.set_state_change_callback(callback)

    def _try_reconnect_camera(self, camera_id: str) -> bool:
        if not self._operation_lock.acquire(blocking=False):
            return False
        try:
            return self._reconnect_owned(camera_id)
        finally:
            self._operation_lock.release()

    def _reconnect_owned(self, camera_id: str) -> bool:
        """Hold reconnect ownership through native work and reject late generations."""
        with self._camera_lock:
            generation = self._generation
            if self._cancel.is_set():
                return False
        is_left = camera_id == "left"
        serial = self._left_id if is_left else self._right_id
        config = self._config
        stop_event = self._frame_router.left_stop if is_left else self._frame_router.right_stop
        if not serial or config is None:
            logger.error("Missing serial or config for %s camera", camera_id)
            return False
        stop_event.set()
        thread = self._frame_router.get_thread(camera_id)
        if thread is not None and thread.is_alive():
            if thread is threading.current_thread():
                return False
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("%s reader is still stopping; reconnect retains the old camera", camera_id)
                return False
        if self._cancel.is_set():
            return False
        old_camera = self._get_camera_fn(camera_id) if self._get_camera_fn else None
        new_camera: Optional[CameraDevice] = None
        published = False
        try:
            if old_camera is not None:
                old_camera.close()
            if self._cancel.is_set():
                return False
            build = self._build_camera_fn
            if build is None:
                return False
            new_camera = build()
            self._factory.open_camera(new_camera, serial, camera_id)
            if self._cancel.is_set():
                return False
            self._factory.configure_camera(new_camera, config, is_left)
            with self._camera_lock:
                if (self._cancel.is_set() or generation != self._generation
                        or not self._frame_router.capture_running):
                    return False
                setter = self._left_ref_setter if is_left else self._right_ref_setter
                assert setter is not None
                setter(new_camera)
                stop_event.clear()
                new_thread = self._frame_router.start_single_thread(camera_id, new_camera, stop_event)
                self._frame_router.set_thread(camera_id, new_thread)
                published = True
            logger.info("Successfully reconnected %s camera", camera_id)
            return True
        except Exception:
            logger.exception("Failed to reconnect %s camera", camera_id)
            return False
        finally:
            if new_camera is not None and not published:
                try:
                    new_camera.close()
                except Exception:
                    self._rejected_cameras.append(new_camera)
                    logger.exception("Failed to close rejected %s camera; retained for stop retry", camera_id)
